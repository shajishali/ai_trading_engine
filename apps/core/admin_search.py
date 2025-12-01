"""
Enhanced Search Functionality for Admin
Provides full-text search, search suggestions, and search history
"""

from django.contrib import admin
from django.db.models import Q
from django.utils.html import format_html
from django.core.cache import cache
from typing import List, Dict


class EnhancedSearchMixin:
    """Mixin to add enhanced search functionality to admin"""
    
    def get_search_results(self, request, queryset, search_term):
        """Enhanced search with full-text search across related models"""
        queryset, use_distinct = super().get_search_results(
            request, queryset, search_term
        )
        
        if search_term:
            # Save search to history
            self._save_search_history(request, search_term)
            
            # Add related model searches
            queryset = self._search_related_models(queryset, search_term)
            use_distinct = True
        
        return queryset, use_distinct
    
    def _search_related_models(self, queryset, search_term):
        """Search across related models"""
        # This should be overridden in subclasses
        return queryset
    
    def _save_search_history(self, request, search_term):
        """Save search term to user's search history"""
        if not hasattr(request, 'user') or not request.user.is_authenticated:
            return
        
        user_id = request.user.id
        cache_key = f'admin_search_history_{user_id}'
        history = cache.get(cache_key, [])
        
        # Add search term if not already in history
        if search_term not in history:
            history.insert(0, search_term)
            # Keep only last 10 searches
            history = history[:10]
            cache.set(cache_key, history, 86400)  # 24 hours
    
    def get_search_suggestions(self, request, search_term):
        """Get search suggestions based on partial search term"""
        if len(search_term) < 2:
            return []
        
        # Get search history
        user_id = request.user.id if request.user.is_authenticated else None
        if user_id:
            cache_key = f'admin_search_history_{user_id}'
            history = cache.get(cache_key, [])
            # Filter history by search term
            suggestions = [h for h in history if search_term.lower() in h.lower()]
            return suggestions[:5]
        
        return []
    
    def get_search_history(self, request):
        """Get user's search history"""
        if not hasattr(request, 'user') or not request.user.is_authenticated:
            return []
        
        user_id = request.user.id
        cache_key = f'admin_search_history_{user_id}'
        return cache.get(cache_key, [])


class FullTextSearchAdmin(EnhancedSearchMixin, admin.ModelAdmin):
    """Admin class with full-text search capabilities"""
    pass


def highlight_search_term(text, search_term):
    """Highlight search term in text"""
    if not search_term or not text:
        return text
    
    import re
    pattern = re.compile(re.escape(search_term), re.IGNORECASE)
    highlighted = pattern.sub(
        lambda m: format_html('<mark>{}</mark>', m.group()),
        str(text)
    )
    return highlighted













