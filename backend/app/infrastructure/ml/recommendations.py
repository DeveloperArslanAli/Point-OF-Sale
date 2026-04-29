"""Product Recommendation Engine - Phase 23.

Implements product recommendations using:
- Association Rules Mining (Apriori/FP-Growth)
- Collaborative Filtering
- Content-based Filtering

Targets: Hit Rate @ K, +10% basket size increase
"""

from __future__ import annotations

import json
import pickle
import structlog
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from itertools import combinations
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

logger = structlog.get_logger(__name__)


@dataclass(slots=True)
class ProductRecommendation:
    """Single product recommendation."""
    product_id: str
    product_name: str
    confidence: float  # Probability of purchase
    support: float     # Frequency in baskets
    lift: float        # Improvement over random
    reason: str        # "frequently_bought_together", "similar_customers", etc.
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "product_id": self.product_id,
            "product_name": self.product_name,
            "confidence": round(self.confidence, 3),
            "support": round(self.support, 4),
            "lift": round(self.lift, 2),
            "reason": self.reason,
        }


@dataclass(slots=True)
class AssociationRule:
    """Market basket association rule."""
    antecedent: frozenset[str]  # If bought these...
    consequent: frozenset[str]  # ...likely to buy these
    support: float
    confidence: float
    lift: float
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "antecedent": list(self.antecedent),
            "consequent": list(self.consequent),
            "support": round(self.support, 4),
            "confidence": round(self.confidence, 3),
            "lift": round(self.lift, 2),
        }


@dataclass(slots=True)
class RecommendationMetrics:
    """Metrics for recommendation model."""
    total_baskets: int
    unique_products: int
    rules_generated: int
    avg_basket_size: float
    min_support: float
    min_confidence: float
    generated_at: datetime


@dataclass
class RecommendationEngine:
    """Product recommendation engine.
    
    Combines association rules mining with collaborative filtering
    to provide accurate product recommendations.
    """
    
    # Association rules parameters
    min_support: float = 0.01   # 1% of baskets
    min_confidence: float = 0.5  # 50% confidence
    min_lift: float = 1.5        # 50% better than random
    max_rules: int = 10000
    
    # Collaborative filtering parameters
    n_similar_users: int = 20
    min_common_purchases: int = 3
    
    # Model data
    _association_rules: list[AssociationRule] = field(default_factory=list, init=False)
    _product_to_rules: dict[str, list[AssociationRule]] = field(default_factory=dict, init=False)
    _product_names: dict[str, str] = field(default_factory=dict, init=False)
    _product_support: dict[str, float] = field(default_factory=dict, init=False)
    _user_purchases: dict[str, set[str]] = field(default_factory=dict, init=False)
    _product_popularity: dict[str, int] = field(default_factory=dict, init=False)
    
    def train_association_rules(
        self,
        transaction_data: pd.DataFrame,
        product_names: dict[str, str] | None = None,
    ) -> RecommendationMetrics:
        """Train association rules model on transaction baskets.
        
        Args:
            transaction_data: DataFrame with columns ['transaction_id', 'product_id']
            product_names: Optional mapping of product_id -> name
            
        Returns:
            Training metrics
        """
        logger.info(
            "training_association_rules",
            min_support=self.min_support,
            min_confidence=self.min_confidence,
        )
        
        if product_names:
            self._product_names = product_names
        
        # Group by transaction to get baskets
        baskets = (
            transaction_data
            .groupby("transaction_id")["product_id"]
            .apply(lambda x: frozenset(x.astype(str)))
            .tolist()
        )
        
        if not baskets:
            logger.warning("no_baskets_found")
            return RecommendationMetrics(
                total_baskets=0,
                unique_products=0,
                rules_generated=0,
                avg_basket_size=0,
                min_support=self.min_support,
                min_confidence=self.min_confidence,
                generated_at=datetime.utcnow(),
            )
        
        n_baskets = len(baskets)
        
        # Calculate item frequencies
        item_counts: Counter[str] = Counter()
        for basket in baskets:
            for item in basket:
                item_counts[item] += 1
        
        # Store product support
        for item, count in item_counts.items():
            self._product_support[item] = count / n_baskets
            self._product_popularity[item] = count
        
        # Filter items by minimum support
        min_count = int(self.min_support * n_baskets)
        frequent_items = {item for item, count in item_counts.items() if count >= min_count}
        
        logger.info(
            "frequent_items_found",
            total_items=len(item_counts),
            frequent_items=len(frequent_items),
        )
        
        # Generate candidate pairs
        pair_counts: Counter[frozenset[str]] = Counter()
        for basket in baskets:
            # Only consider frequent items
            frequent_in_basket = basket & frequent_items
            if len(frequent_in_basket) >= 2:
                for pair in combinations(frequent_in_basket, 2):
                    pair_counts[frozenset(pair)] += 1
        
        # Generate association rules from frequent pairs
        rules = []
        for pair, count in pair_counts.items():
            pair_support = count / n_baskets
            if pair_support < self.min_support:
                continue
            
            pair_list = list(pair)
            
            # Generate rules in both directions
            for i in range(2):
                antecedent = frozenset([pair_list[i]])
                consequent = frozenset([pair_list[1 - i]])
                
                ant_support = item_counts[pair_list[i]] / n_baskets
                confidence = pair_support / ant_support if ant_support > 0 else 0
                
                cons_support = item_counts[pair_list[1 - i]] / n_baskets
                lift = confidence / cons_support if cons_support > 0 else 0
                
                if confidence >= self.min_confidence and lift >= self.min_lift:
                    rules.append(AssociationRule(
                        antecedent=antecedent,
                        consequent=consequent,
                        support=pair_support,
                        confidence=confidence,
                        lift=lift,
                    ))
        
        # Sort by lift and limit
        rules.sort(key=lambda r: r.lift, reverse=True)
        self._association_rules = rules[:self.max_rules]
        
        # Index rules by antecedent products
        self._product_to_rules = defaultdict(list)
        for rule in self._association_rules:
            for product in rule.antecedent:
                self._product_to_rules[product].append(rule)
        
        avg_basket_size = sum(len(b) for b in baskets) / n_baskets
        
        metrics = RecommendationMetrics(
            total_baskets=n_baskets,
            unique_products=len(item_counts),
            rules_generated=len(self._association_rules),
            avg_basket_size=avg_basket_size,
            min_support=self.min_support,
            min_confidence=self.min_confidence,
            generated_at=datetime.utcnow(),
        )
        
        logger.info(
            "association_rules_trained",
            rules_generated=len(self._association_rules),
            baskets=n_baskets,
            products=len(item_counts),
        )
        
        return metrics
    
    def train_collaborative(
        self,
        transaction_data: pd.DataFrame,
    ) -> None:
        """Build user-item purchase matrix for collaborative filtering.
        
        Args:
            transaction_data: DataFrame with ['customer_id', 'product_id']
        """
        # Build user purchase sets
        user_purchases: dict[str, set[str]] = defaultdict(set)
        
        for _, row in transaction_data.iterrows():
            customer_id = str(row.get("customer_id", ""))
            if customer_id and customer_id != "None":
                user_purchases[customer_id].add(str(row["product_id"]))
        
        self._user_purchases = dict(user_purchases)
        
        logger.info(
            "collaborative_model_built",
            users=len(self._user_purchases),
        )
    
    def get_recommendations(
        self,
        cart_products: list[str],
        customer_id: str | None = None,
        n_recommendations: int = 5,
        exclude_cart: bool = True,
    ) -> list[ProductRecommendation]:
        """Get product recommendations based on cart contents.
        
        Args:
            cart_products: Products currently in cart
            customer_id: Optional customer for personalization
            n_recommendations: Number of recommendations to return
            exclude_cart: Whether to exclude cart products from recommendations
            
        Returns:
            List of ProductRecommendation objects
        """
        cart_set = set(str(p) for p in cart_products)
        recommendations: dict[str, ProductRecommendation] = {}
        
        # 1. Association rules recommendations
        for product in cart_products:
            product_str = str(product)
            rules = self._product_to_rules.get(product_str, [])
            
            for rule in rules:
                for recommended in rule.consequent:
                    if exclude_cart and recommended in cart_set:
                        continue
                    
                    # If already recommended, keep the one with higher lift
                    if recommended in recommendations:
                        if rule.lift > recommendations[recommended].lift:
                            recommendations[recommended] = ProductRecommendation(
                                product_id=recommended,
                                product_name=self._product_names.get(recommended, recommended),
                                confidence=rule.confidence,
                                support=rule.support,
                                lift=rule.lift,
                                reason="frequently_bought_together",
                            )
                    else:
                        recommendations[recommended] = ProductRecommendation(
                            product_id=recommended,
                            product_name=self._product_names.get(recommended, recommended),
                            confidence=rule.confidence,
                            support=rule.support,
                            lift=rule.lift,
                            reason="frequently_bought_together",
                        )
        
        # 2. Collaborative filtering recommendations
        if customer_id and customer_id in self._user_purchases:
            customer_purchases = self._user_purchases[customer_id]
            
            # Find similar users
            similar_users = self._find_similar_users(customer_id, customer_purchases)
            
            # Get products from similar users
            for similar_user, similarity in similar_users[:self.n_similar_users]:
                similar_user_products = self._user_purchases.get(similar_user, set())
                new_products = similar_user_products - customer_purchases - cart_set
                
                for product in new_products:
                    if product not in recommendations:
                        recommendations[product] = ProductRecommendation(
                            product_id=product,
                            product_name=self._product_names.get(product, product),
                            confidence=similarity,
                            support=self._product_support.get(product, 0),
                            lift=1.0 + similarity,
                            reason="similar_customers",
                        )
        
        # 3. Fallback to popular items if not enough recommendations
        if len(recommendations) < n_recommendations:
            popular_products = sorted(
                self._product_popularity.items(),
                key=lambda x: x[1],
                reverse=True
            )
            
            for product, count in popular_products:
                if product not in recommendations and (not exclude_cart or product not in cart_set):
                    recommendations[product] = ProductRecommendation(
                        product_id=product,
                        product_name=self._product_names.get(product, product),
                        confidence=0.5,
                        support=self._product_support.get(product, 0),
                        lift=1.0,
                        reason="popular_item",
                    )
                    
                    if len(recommendations) >= n_recommendations:
                        break
        
        # Sort by lift * confidence and return top N
        sorted_recs = sorted(
            recommendations.values(),
            key=lambda r: r.lift * r.confidence,
            reverse=True
        )
        
        return sorted_recs[:n_recommendations]
    
    def _find_similar_users(
        self,
        customer_id: str,
        customer_purchases: set[str],
    ) -> list[tuple[str, float]]:
        """Find users with similar purchase patterns.
        
        Returns list of (user_id, similarity_score) tuples.
        """
        similarities: list[tuple[str, float]] = []
        
        for other_id, other_purchases in self._user_purchases.items():
            if other_id == customer_id:
                continue
            
            # Jaccard similarity
            intersection = len(customer_purchases & other_purchases)
            if intersection < self.min_common_purchases:
                continue
            
            union = len(customer_purchases | other_purchases)
            similarity = intersection / union if union > 0 else 0
            
            if similarity > 0.1:
                similarities.append((other_id, similarity))
        
        similarities.sort(key=lambda x: x[1], reverse=True)
        return similarities
    
    def get_frequently_bought_together(
        self,
        product_id: str,
        n_results: int = 5,
    ) -> list[ProductRecommendation]:
        """Get products frequently bought with a specific product.
        
        Args:
            product_id: Product to find associations for
            n_results: Number of results to return
            
        Returns:
            List of associated products
        """
        product_str = str(product_id)
        rules = self._product_to_rules.get(product_str, [])
        
        recommendations = []
        seen = set()
        
        for rule in sorted(rules, key=lambda r: r.lift, reverse=True):
            for product in rule.consequent:
                if product not in seen:
                    recommendations.append(ProductRecommendation(
                        product_id=product,
                        product_name=self._product_names.get(product, product),
                        confidence=rule.confidence,
                        support=rule.support,
                        lift=rule.lift,
                        reason="frequently_bought_together",
                    ))
                    seen.add(product)
                    
                    if len(recommendations) >= n_results:
                        return recommendations
        
        return recommendations
    
    def suggest_bundles(
        self,
        cart_products: list[str],
        min_bundle_size: int = 2,
        max_bundle_size: int = 4,
    ) -> list[dict[str, Any]]:
        """Suggest product bundles based on cart contents.
        
        Returns bundle suggestions with potential discount impact.
        """
        cart_set = set(str(p) for p in cart_products)
        bundles = []
        
        # Find products commonly bought together
        recommendations = self.get_recommendations(
            cart_products,
            n_recommendations=max_bundle_size,
            exclude_cart=True,
        )
        
        if not recommendations:
            return bundles
        
        # Create bundle suggestions
        for size in range(min_bundle_size, max_bundle_size + 1):
            if len(recommendations) >= size:
                bundle_products = recommendations[:size]
                
                # Calculate average lift as bundle strength
                avg_lift = sum(p.lift for p in bundle_products) / len(bundle_products)
                avg_confidence = sum(p.confidence for p in bundle_products) / len(bundle_products)
                
                bundles.append({
                    "products": [p.to_dict() for p in bundle_products],
                    "bundle_strength": round(avg_lift, 2),
                    "purchase_probability": round(avg_confidence, 3),
                    "suggested_discount_percent": min(15, int(avg_lift * 5)),
                })
        
        return bundles
    
    def get_all_rules(self) -> list[dict[str, Any]]:
        """Get all association rules for export/analysis."""
        return [rule.to_dict() for rule in self._association_rules]
    
    def save_model(self, path: Path) -> None:
        """Save trained model to disk."""
        path.mkdir(parents=True, exist_ok=True)
        
        # Save association rules
        with open(path / "association_rules.pkl", "wb") as f:
            pickle.dump(self._association_rules, f)
        
        # Save product data
        with open(path / "product_data.json", "w") as f:
            json.dump({
                "names": self._product_names,
                "support": self._product_support,
                "popularity": self._product_popularity,
            }, f)
        
        # Save user purchases
        with open(path / "user_purchases.pkl", "wb") as f:
            pickle.dump(self._user_purchases, f)
        
        # Save config
        config = {
            "min_support": self.min_support,
            "min_confidence": self.min_confidence,
            "min_lift": self.min_lift,
            "max_rules": self.max_rules,
        }
        with open(path / "config.json", "w") as f:
            json.dump(config, f)
        
        logger.info("recommendation_model_saved", path=str(path))
    
    def load_model(self, path: Path) -> None:
        """Load trained model from disk."""
        rules_path = path / "association_rules.pkl"
        if rules_path.exists():
            with open(rules_path, "rb") as f:
                self._association_rules = pickle.load(f)
            
            # Rebuild index
            self._product_to_rules = defaultdict(list)
            for rule in self._association_rules:
                for product in rule.antecedent:
                    self._product_to_rules[product].append(rule)
        
        product_path = path / "product_data.json"
        if product_path.exists():
            with open(product_path) as f:
                data = json.load(f)
                self._product_names = data.get("names", {})
                self._product_support = data.get("support", {})
                self._product_popularity = data.get("popularity", {})
        
        purchases_path = path / "user_purchases.pkl"
        if purchases_path.exists():
            with open(purchases_path, "rb") as f:
                self._user_purchases = pickle.load(f)
        
        config_path = path / "config.json"
        if config_path.exists():
            with open(config_path) as f:
                config = json.load(f)
                self.min_support = config.get("min_support", 0.01)
                self.min_confidence = config.get("min_confidence", 0.5)
                self.min_lift = config.get("min_lift", 1.5)
        
        logger.info("recommendation_model_loaded", path=str(path))


def create_recommendation_engine(
    min_support: float = 0.01,
    min_confidence: float = 0.5,
    min_lift: float = 1.5,
) -> RecommendationEngine:
    """Factory function to create a recommendation engine."""
    return RecommendationEngine(
        min_support=min_support,
        min_confidence=min_confidence,
        min_lift=min_lift,
    )
