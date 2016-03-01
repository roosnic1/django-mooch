from __future__ import unicode_literals

from decimal import Decimal
import uuid

from django.db import models
from django.db.models import Count, Sum
from django.utils import timezone
from django.utils.encoding import python_2_unicode_compatible
from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _, ugettext


class ProjectManager(models.Manager):
    def current(self):
        return self.filter(is_active=True).order_by('created_at').first()


@python_2_unicode_compatible
class Project(models.Model):
    created_at = models.DateTimeField(
        _('created at'),
        default=timezone.now,
    )
    is_active = models.BooleanField(
        _('is active'),
        default=True,
    )
    title = models.CharField(
        _('title'),
        max_length=200,
    )
    funding_goal = models.DecimalField(
        _('funding goal'),
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
    )
    default_amount = models.DecimalField(
        _('default amount'),
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
    )

    objects = ProjectManager()

    class Meta:
        ordering = ('-created_at',)
        verbose_name = _('project')
        verbose_name_plural = _('projects')

    def __str__(self):
        return self.title

    @cached_property
    def donation_total(self):
        return self.donation_set.order_by().filter(
            charged_at__isnull=False,
        ).aggregate(s=Sum('amount'))['s'] or Decimal('0')

    @cached_property
    def funding_percentage(self):
        if not self.funding_goal:
            return '-'
        return 100 * self.donation_total / self.funding_goal

    @cached_property
    def available_rewards(self):
        donation_count = Donation.objects.order_by().filter(
            project=self,
            charged_at__isnull=False,
        ).values('selected_reward').annotate(Count('id'))
        donation_count = {
            r['selected_reward']: r['id__count']
            for r in donation_count
        }

        return [
            reward for reward in self.rewards.all()
            if reward.available_times is None or
            donation_count.get(reward.id, 0) < reward.available_times
        ]


@python_2_unicode_compatible
class Reward(models.Model):
    project = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        verbose_name=_('project'),
        related_name='rewards',
    )
    title = models.CharField(
        _('title'),
        max_length=200,
    )
    available_times = models.PositiveIntegerField(
        _('available'),
        blank=True,
        null=True,
        help_text=_('Leave empty if availability is unlimited.'),
    )
    donation_amount = models.DecimalField(
        _('donation amount'),
        max_digits=10,
        decimal_places=2,
        help_text=_('The donation has to be at least this amount.'),
    )

    class Meta:
        ordering = ('donation_amount',)
        verbose_name = _('reward')
        verbose_name_plural = _('rewards')

    def __str__(self):
        return ugettext('%(title)s (from %(amount)s)') % {
            'title': self.title,
            'amount': self.donation_amount,
        }


@python_2_unicode_compatible
class Donation(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    project = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        verbose_name=_('project'),
    )
    created_at = models.DateTimeField(
        _('created at'),
        default=timezone.now,
    )
    charged_at = models.DateTimeField(
        _('charged at'),
        blank=True,
        null=True,
    )
    amount = models.DecimalField(
        _('amount'),
        max_digits=10,
        decimal_places=2,
    )
    selected_reward = models.ForeignKey(
        Reward,
        on_delete=models.PROTECT,
        verbose_name=_('selected reward'),
        blank=True,
        null=True,
        related_name='donations',
    )

    full_name = models.CharField(
        _('full name'),
        max_length=200,
    )
    email = models.EmailField(
        _('email'),
        max_length=254,
    )
    postal_address = models.TextField(
        _('postal address'),
        blank=True,
    )

    transaction = models.TextField(
        _('transaction'),
        blank=True,
    )

    class Meta:
        ordering = ('-created_at',)
        verbose_name = _('donation')
        verbose_name_plural = _('donations')

    @property
    def amount_cents(self):
        return int(self.amount * 100)

    def __str__(self):
        return '%s for %s' % (self.amount, self.project)
