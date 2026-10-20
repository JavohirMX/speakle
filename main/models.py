from django.db import models


class PageStat(models.Model):
    """One aggregate counter per day and key. No IPs, cookies, user ids or raw paths are stored.

    Keys: ``view:<route name>``, ``ref:<referrer host>``, ``src:<utm_source>``.
    """
    day = models.DateField(db_index=True)
    key = models.CharField(max_length=80)
    count = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['day', 'key'], name='uniq_pagestat_day_key')]

    def __str__(self):
        return f'{self.day} {self.key} = {self.count}'
