from django.db import models

class State(models.Model):
    name = models.CharField(max_length=100, unique=True, db_index=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class District(models.Model):
    state = models.ForeignKey(State, on_delete=models.CASCADE, related_name='districts')
    name = models.CharField(max_length=100, db_index=True)

    class Meta:
        ordering = ['name']
        unique_together = ('state', 'name')

    def __str__(self):
        return f"{self.name}, {self.state.name}"


class City(models.Model):
    district = models.ForeignKey(District, on_delete=models.CASCADE, related_name='cities')
    name = models.CharField(max_length=100, db_index=True)

    class Meta:
        ordering = ['name']
        verbose_name_plural = "Cities"
        unique_together = ('district', 'name')

    def __str__(self):
        return f"{self.name} ({self.district.name})"