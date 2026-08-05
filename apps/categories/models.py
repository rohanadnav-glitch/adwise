from django.db import models

class Category(models.Model):
    name = models.CharField(max_length=100, unique=True, db_index=True)
    description = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['name']
        verbose_name_plural = "Categories"

    def __str__(self):
        return self.name


class SubCategory(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='subcategories')
    name = models.CharField(max_length=100, db_index=True)

    class Meta:
        ordering = ['name']
        verbose_name_plural = "SubCategories"
        unique_together = ('category', 'name')

    def __str__(self):
        return f"{self.name} ({self.category.name})"