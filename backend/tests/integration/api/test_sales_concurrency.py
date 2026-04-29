import asyncio
import pytest
from decimal import Decimal
from app.application.sales.use_cases.record_sale import (
    RecordSaleUseCase,
    RecordSaleInput,
    SaleLineInput,
    SalePaymentInput,
)
from app.infrastructure.db.repositories.inventory_repository import SqlAlchemyProductRepository
from app.infrastructure.db.repositories.sales_repository import SqlAlchemySalesRepository
from app.infrastructure.db.repositories.inventory_movement_repository import SqlAlchemyInventoryMovementRepository
from app.domain.catalog.entities import Product
from app.domain.common.money import Money
from app.domain.inventory import InventoryMovement, MovementDirection
# Ensure models are loaded
import app.infrastructure.db.models.customer_model

@pytest.mark.asyncio
async def test_concurrent_sales_stock_check(async_session):
    # Setup Repos
    product_repo = SqlAlchemyProductRepository(async_session)
    sales_repo = SqlAlchemySalesRepository(async_session)
    inventory_repo = SqlAlchemyInventoryMovementRepository(async_session)

    # 1. Create Product
    import uuid
    sku = f"CONC-{uuid.uuid4().hex[:8]}"
    product = Product.create(
        name="Concurrency Test Item",
        sku=sku,
        price_retail=Decimal("10.00"),
        purchase_price=Decimal("5.00"),
        category_id=None
    )
    await product_repo.add(product)
    
    # 2. Add Stock (10 items)
    movement = InventoryMovement.record(
        product_id=product.id,
        quantity=10,
        direction=MovementDirection.IN,
        reason="initial_stock",
        reference="setup"
    )
    await inventory_repo.add(movement)
    await async_session.commit()

    # 3. Define the sale task
    async def attempt_sale():
        # We need a new session for each "task" to simulate concurrent transactions
        # But here we are in one test function. 
        # To truly test DB locking, we need separate DB sessions/connections.
        # Since async_session fixture gives one session, we might need to create new ones.
        
        from app.infrastructure.db.session import async_session_factory
        async with async_session_factory() as session:
            p_repo = SqlAlchemyProductRepository(session)
            s_repo = SqlAlchemySalesRepository(session)
            i_repo = SqlAlchemyInventoryMovementRepository(session)
            
            use_case = RecordSaleUseCase(p_repo, s_repo, i_repo)
            input_data = RecordSaleInput(
                lines=[SaleLineInput(product_id=product.id, quantity=1, unit_price=Decimal("10.00"))],
                payments=[
                    SalePaymentInput(payment_method="cash", amount=Decimal("10.00"))
                ],
            )
            try:
                await use_case.execute(input_data)
                await session.commit()
                return True
            except Exception as e:
                print(f"Sale failed: {e}")
                await session.rollback()
                return False
    # 4. Run 20 concurrent sales
    tasks = [attempt_sale() for _ in range(20)]
    results = await asyncio.gather(*tasks)

    # 5. Verify results
    success_count = sum(1 for r in results if r)
    fail_count = sum(1 for r in results if not r)

    print(f"Success: {success_count}, Fail: {fail_count}")

    # We expect at most 10 successes (stock 10)
    # Due to optimistic locking, many might fail with ConflictError, so success_count can be < 10
    assert success_count <= 10
    
    # Verify final stock matches
    stock = await inventory_repo.get_stock_level(product.id)
    assert stock.quantity_on_hand == 10 - success_count
    assert stock.quantity_on_hand >= 0
