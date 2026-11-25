from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import models
from django.db.models import Q
from PIL import Image, ImageOps


def optimize_uploaded_image(image_field, max_size: tuple[int, int], quality: int = 82) -> None:
    """
    Resizes and compresses a newly uploaded ImageField in memory before saving to disk.
    Skips images that are already committed to storage.
    """
    if not image_field or getattr(image_field, "_committed", True):
        return

    image_field.seek(0)
    with Image.open(image_field) as img:
        img = ImageOps.exif_transpose(img)
        img.thumbnail(max_size, Image.Resampling.LANCZOS)

        output = BytesIO()
        original_stem = Path(image_field.name).stem
        has_alpha = img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info)

        if has_alpha:
            if img.mode != "RGBA":
                img = img.convert("RGBA")
            img.save(output, format="PNG", optimize=True)
            new_filename = f"{original_stem}.png"
        else:
            if img.mode != "RGB":
                img = img.convert("RGB")
            img.save(output, format="JPEG", quality=quality, optimize=True)
            new_filename = f"{original_stem}.jpg"

    output.seek(0)
    image_field.save(new_filename, ContentFile(output.read()), save=False)


class RoleChoices(models.TextChoices):
    TOP = "TOP", "Top"
    BOTTOM = "BOTTOM", "Bottom"
    SWITCH = "SWITCH", "Switch"


class Member(AbstractUser):
    role = models.CharField(
        max_length=10,
        choices=RoleChoices.choices,
        default=RoleChoices.SWITCH,
        help_text="Primary club play role.",
    )
    profile_picture = models.ImageField(
        upload_to="profile_pictures/%Y/%m/",
        blank=True,
        null=True,
        help_text="Optional profile picture visible to other approved members.",
    )
    bio = models.TextField(
        blank=True,
        help_text="Optional member profile notes visible to other approved members.",
    )
    must_change_password = models.BooleanField(
        default=False,
        help_text="If True, user is forced to change their password upon next login.",
    )

    def save(self, *args, **kwargs):
        optimize_uploaded_image(self.profile_picture, max_size=(500, 500), quality=85)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.username} ({self.get_role_display()})"


class VettingApplication(models.Model):
    rl_name = models.CharField(max_length=150, verbose_name="RL Name")
    fetlife_name = models.CharField(max_length=150, verbose_name="FetLife Profile Name")
    applicant_name = models.CharField(max_length=150, verbose_name="Preferred Name or Scene Alias")
    email = models.EmailField(unique=True)
    role = models.CharField(
        max_length=10,
        choices=RoleChoices.choices,
        blank=True,
        default="",
    )
    is_reference = models.BooleanField(
        default=False,
        help_text="True if submitted via the 'Apply with References' form.",
    )
    vetting_answers = models.JSONField(
        default=dict,
        help_text="Stores question labels and applicant responses or references.",
    )
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-submitted_at"]
        verbose_name = "Vetting Application"
        verbose_name_plural = "Vetting Applications"

    def __str__(self) -> str:
        app_type = "Reference" if self.is_reference else self.get_role_display()
        return f"{self.applicant_name} ({app_type}) — {self.email}"


class Event(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    event_date = models.DateTimeField()
    location = models.CharField(max_length=255)
    is_rsvp_open = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["event_date"]

    def __str__(self) -> str:
        return f"{self.title} ({self.event_date.strftime('%Y-%m-%d')})"


class RSVP(models.Model):
    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name="rsvps",
    )
    member = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="rsvps",
    )
    attending = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["event", "member"],
                name="unique_event_member_rsvp",
            )
        ]
        verbose_name = "RSVP"
        verbose_name_plural = "RSVPs"

    def __str__(self) -> str:
        status = "Attending" if self.attending else "Not Attending"
        return f"{self.member.username} - {self.event.title} ({status})"


class ForumTopic(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_topics",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.title


class ForumPost(models.Model):
    topic = models.ForeignKey(
        ForumTopic,
        on_delete=models.CASCADE,
        related_name="posts",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="forum_posts",
    )
    body = models.TextField(blank=True)
    image = models.ImageField(
        upload_to="forum_images/%Y/%m/",
        blank=True,
        null=True,
        help_text="Optional image attachment (JPG, PNG, GIF, or WebP).",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def save(self, *args, **kwargs):
        optimize_uploaded_image(self.image, max_size=(1200, 1200), quality=82)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"Post by {self.author.username} in {self.topic.title}"


class MessageConsent(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        ACCEPTED = "ACCEPTED", "Accepted"
        REVOKED = "REVOKED", "Revoked"

    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_consent_requests",
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="received_consent_requests",
    )
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["requester", "recipient"],
                name="unique_consent_pair",
            )
        ]

    def __str__(self) -> str:
        return f"{self.requester.username} -> {self.recipient.username} ({self.status})"

    def revoke(self) -> None:
        self.status = self.Status.REVOKED
        self.save(update_fields=["status", "updated_at"])

    @classmethod
    def has_active_consent(cls, user_a, user_b) -> bool:
        return cls.objects.filter(
            Q(requester=user_a, recipient=user_b) | Q(requester=user_b, recipient=user_a),
            status=cls.Status.ACCEPTED,
        ).exists()


class DirectMessage(models.Model):
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_messages",
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="received_messages",
    )
    body = models.TextField()
    sent_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ["sent_at"]

    def __str__(self) -> str:
        return f"From {self.sender.username} to {self.recipient.username} at {self.sent_at:%Y-%m-%d %H:%M}"

    def clean(self) -> None:
        super().clean()
        if self.sender_id and self.recipient_id:
            if not MessageConsent.has_active_consent(self.sender, self.recipient):
                raise ValidationError(
                    "Direct messages require active mutual consent between both members."
                )