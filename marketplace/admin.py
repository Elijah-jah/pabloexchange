from django.contrib import admin

from .models import (LogCategory, LogGroup, LogItem, LogOrder,
                     LogSubCategory)


class LogSubCategoryInline(admin.StackedInline):
    model = LogSubCategory
    extra = 0


@admin.register(LogCategory)
class LogCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'order', 'is_active')
    list_editable = ('order', 'is_active')
    inlines = [LogSubCategoryInline]


@admin.register(LogSubCategory)
class LogSubCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'order', 'is_active')
    list_filter = ('category',)
    list_editable = ('order', 'is_active')


class LogItemInline(admin.TabularInline):
    """Credential lines — add rows here to restock."""
    model = LogItem
    extra = 3
    fields = ('content', 'is_sold', 'sold_at')
    readonly_fields = ('sold_at',)


@admin.register(LogGroup)
class LogGroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'subcategory', 'price', 'stock', 'actual_stock',
                    'is_active', 'created_at')
    list_filter = ('subcategory__category', 'subcategory', 'is_active')
    search_fields = ('name', 'description')
    list_editable = ('price', 'stock', 'is_active')
    inlines = [LogItemInline]


@admin.register(LogItem)
class LogItemAdmin(admin.ModelAdmin):
    """Quick stock-management view: see every credential line."""
    list_display = ('short_content', 'group', 'is_sold', 'sold_at')
    list_filter = ('group__subcategory__category', 'group', 'is_sold')
    search_fields = ('content', 'group__name')
    readonly_fields = ('sold_at',)

    def short_content(self, obj):
        return obj.content[:60] + ('…' if len(obj.content) > 60 else '')
    short_content.short_description = 'Credentials'


@admin.register(LogOrder)
class LogOrderAdmin(admin.ModelAdmin):
    list_display = ('group_name', 'user', 'price', 'created_at')
    search_fields = ('group_name', 'user__username')
    readonly_fields = ('user', 'group', 'group_name', 'price', 'credentials', 'created_at')

    def has_add_permission(self, request):
        return False