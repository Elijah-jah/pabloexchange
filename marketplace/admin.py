from django.contrib import admin

from .models import (LogCategory, LogCredential, LogGroup, LogItem,
                     LogOrder, LogSubCategory)


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


class LogGroupInline(admin.StackedInline):
    model = LogGroup
    extra = 0


@admin.register(LogGroup)
class LogGroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'subcategory', 'is_active')
    list_filter = ('subcategory__category', 'subcategory')


class LogCredentialInline(admin.TabularInline):
    model = LogCredential
    extra = 5
    fields = ('content', 'is_sold', 'sold_at')
    readonly_fields = ('sold_at',)


@admin.register(LogItem)
class LogItemAdmin(admin.ModelAdmin):
    list_display = ('title', 'group', 'price', 'stock', 'is_active', 'created_at')
    list_filter = ('group__subcategory__category', 'group__subcategory', 'is_active')
    search_fields = ('title', 'description')
    list_editable = ('price', 'stock', 'is_active')
    inlines = [LogCredentialInline]


@admin.register(LogOrder)
class LogOrderAdmin(admin.ModelAdmin):
    list_display = ('item_title', 'user', 'price', 'created_at')
    search_fields = ('item_title', 'user__username')
    readonly_fields = ('user', 'item', 'item_title', 'price', 'credentials', 'created_at')

    def has_add_permission(self, request):
        return False