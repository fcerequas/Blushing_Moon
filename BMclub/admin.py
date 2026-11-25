import secrets
import string
from django.conf import settings
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin
from django.core.mail import send_mail
from django.db.models import Count, Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import path, reverse
from django.utils.html import format_html, format_html_join
from django.utils.text import slugify

from .models import (
    DirectMessage,
    Event,
    ForumPost,
    ForumTopic,
    Member,
    MessageConsent,
    RoleChoices,
    RSVP,
    VettingApplication,
)


def generate_temp_password(length: int = 12) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def generate_unique_username(applicant_name: str, email: str) -> str:
    base = slugify(applicant_name).replace("-", "_")
    if not base:
        base = slugify(email.split("@")[0]).replace("-", "_") or "member"
    username = base
    counter = 1
    while Member.objects.filter(username__iexact=username).exists():
        username = f"{base}_{counter}"
        counter += 1
    return username


@admin.register(Member)
class MemberAdmin(UserAdmin):
    list_display = (
        "username",
        "email",
        "first_name",
        "role",
        "is_active",
        "must_change_password",
        "is_staff",
        "delete_member_button",
    )
    list_filter = ("role", "is_active", "must_change_password", "is_staff")
    search_fields = ("username", "email", "first_name", "last_name")
    fieldsets = UserAdmin.fieldsets + (
        ("Club Profile & Security", {"fields": ("role", "profile_picture", "bio", "must_change_password")}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Club Profile & Security", {"fields": ("email", "first_name", "role", "profile_picture", "bio", "must_change_password")}),
    )

    @admin.display(description="Remove")
    def delete_member_button(self, obj: Member):
        if obj.is_superuser:
            return "-"
        delete_url = reverse("admin:bmclub_member_delete", args=[obj.pk])
        return format_html(
            '<a class="button" style="background-color: #dc3545; color: white; padding: 4px 10px; border-radius: 4px; text-decoration: none;" href="{}">Delete</a>',
            delete_url,
        )


@admin.register(VettingApplication)
class VettingApplicationAdmin(admin.ModelAdmin):
    list_display = (
        "applicant_name",
        "rl_name",
        "fetlife_name",
        "email",
        "application_type",
        "submitted_at",
        "decision_buttons",
    )
    list_filter = ("is_reference", "role", "submitted_at")
    search_fields = ("applicant_name", "rl_name", "fetlife_name", "email")
    readonly_fields = (
        "rl_name",
        "fetlife_name",
        "applicant_name",
        "email",
        "application_type",
        "submitted_at",
        "formatted_answers",
        "decision_buttons",
    )
    exclude = ("vetting_answers", "role", "is_reference")

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<int:pk>/approve/",
                self.admin_site.admin_view(self.approve_application_view),
                name="bmclub_vettingapplication_approve",
            ),
            path(
                "<int:pk>/reject/",
                self.admin_site.admin_view(self.reject_application_view),
                name="bmclub_vettingapplication_reject",
            ),
        ]
        return custom_urls + urls

    @admin.display(description="Application Type / Role")
    def application_type(self, obj: VettingApplication) -> str:
        if obj.is_reference:
            return "Reference Application"
        return obj.get_role_display() or "General"

    @admin.display(description="Vetting Answers / References")
    def formatted_answers(self, obj: VettingApplication):
        if not obj.vetting_answers:
            return "No answers recorded."
        return format_html(
            '<div style="max-width: 800px; line-height: 1.5;">{}</div>',
            format_html_join(
                "",
                '<div style="margin-bottom: 14px; padding: 10px; background: #f8f9fa; color: #212529; border-left: 4px solid #dc3545; border-radius: 4px;">'
                "<strong>{}</strong><br><span style='white-space: pre-wrap;'>{}</span></div>",
                ((q, a) for q, a in obj.vetting_answers.items()),
            ),
        )

    @admin.display(description="Quick Decision")
    def decision_buttons(self, obj: VettingApplication):
        if not obj.pk:
            return "-"
        approve_url = reverse("admin:bmclub_vettingapplication_approve", args=[obj.pk])
        reject_url = reverse("admin:bmclub_vettingapplication_reject", args=[obj.pk])
        return format_html(
            '<a class="button" style="background-color: #198754; color: white; padding: 5px 10px; margin-right: 8px; border-radius: 4px; text-decoration: none;" href="{}">Approve</a>'
            '<a class="button" style="background-color: #dc3545; color: white; padding: 5px 10px; border-radius: 4px; text-decoration: none;" href="{}" onclick="return confirm(\'Reject and delete this application?\');">Reject</a>',
            approve_url,
            reject_url,
        )

    def approve_application_view(self, request: HttpRequest, pk: int) -> HttpResponse:
        app = get_object_or_404(VettingApplication, pk=pk)
        if Member.objects.filter(email__iexact=app.email).exists():
            messages.error(request, f"A member with email {app.email} already exists.")
            return redirect("admin:bmclub_vettingapplication_changelist")

        username = generate_unique_username(app.applicant_name, app.email)
        temp_password = generate_temp_password()
        assigned_role = app.role if app.role in RoleChoices.values else RoleChoices.SWITCH

        member = Member.objects.create_user(
            username=username,
            email=app.email,
            password=temp_password,
            first_name=app.applicant_name,
            role=assigned_role,
            must_change_password=True,
        )

        login_url = request.build_absolute_uri(reverse("login"))
        send_mail(
            subject="Welcome to Blushing Moon — Your Member Login",
            message=(
                f"Hello {app.applicant_name},\n\n"
                f"Your application for Blushing Moon has been approved!\n\n"
                f"Here are your temporary login credentials:\n"
                f"Login URL: {login_url}\n"
                f"Username: {member.username}\n"
                f"Temporary Password: {temp_password}\n\n"
                f"When you sign in for the first time, you will be prompted to set a new private password and review your member profile."
            ),
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@blushingmoon.local"),
            recipient_list=[app.email],
            fail_silently=True,
        )

        app.delete()
        messages.success(
            request,
            f"Approved {member.first_name}! Created user '{member.username}' (Temp password: {temp_password}) and removed the application.",
        )
        return redirect("admin:bmclub_vettingapplication_changelist")

    def reject_application_view(self, request: HttpRequest, pk: int) -> HttpResponse:
        app = get_object_or_404(VettingApplication, pk=pk)
        applicant_name = app.applicant_name
        applicant_email = app.email

        send_mail(
            subject="Update Regarding Your Blushing Moon Application",
            message=(
                f"Hello {applicant_name},\n\n"
                f"Thank you for taking the time to submit an application for Blushing Moon. "
                f"After reviewing your submission, we are unable to approve your membership application at this time."
            ),
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@blushingmoon.local"),
            recipient_list=[applicant_email],
            fail_silently=True,
        )

        app.delete()
        messages.warning(request, f"Rejected and deleted application for {applicant_name} ({applicant_email}).")
        return redirect("admin:bmclub_vettingapplication_changelist")


class RSVPInline(admin.TabularInline):
    model = RSVP
    extra = 0
    readonly_fields = ("member_role", "updated_at")
    fields = ("member", "member_role", "attending", "updated_at")

    @admin.display(description="Role")
    def member_role(self, obj: RSVP) -> str:
        return obj.member.get_role_display()


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "event_date",
        "location",
        "is_rsvp_open",
        "total_attending",
        "tops_count",
        "bottoms_count",
        "switches_count",
    )
    list_filter = ("is_rsvp_open", "event_date")
    search_fields = ("title", "location")
    inlines = [RSVPInline]

    def get_queryset(self, request: HttpRequest):
        qs = super().get_queryset(request)
        return qs.annotate(
            _total_attending=Count("rsvps", filter=Q(rsvps__attending=True)),
            _tops=Count("rsvps", filter=Q(rsvps__attending=True, rsvps__member__role=RoleChoices.TOP)),
            _bottoms=Count("rsvps", filter=Q(rsvps__attending=True, rsvps__member__role=RoleChoices.BOTTOM)),
            _switches=Count("rsvps", filter=Q(rsvps__attending=True, rsvps__member__role=RoleChoices.SWITCH)),
        )

    @admin.display(description="Total Attending", ordering="_total_attending")
    def total_attending(self, obj) -> int:
        return obj._total_attending

    @admin.display(description="Tops", ordering="_tops")
    def tops_count(self, obj) -> int:
        return obj._tops

    @admin.display(description="Bottoms", ordering="_bottoms")
    def bottoms_count(self, obj) -> int:
        return obj._bottoms

    @admin.display(description="Switches", ordering="_switches")
    def switches_count(self, obj) -> int:
        return obj._switches


@admin.register(ForumTopic)
class ForumTopicAdmin(admin.ModelAdmin):
    list_display = ("title", "created_by", "created_at")
    search_fields = ("title", "description")


@admin.register(ForumPost)
class ForumPostAdmin(admin.ModelAdmin):
    list_display = ("topic", "author", "has_image", "created_at")
    list_filter = ("topic", "created_at")
    search_fields = ("body", "author__username")
    readonly_fields = ("image_preview",)

    @admin.display(boolean=True, description="Image")
    def has_image(self, obj: ForumPost) -> bool:
        return bool(obj.image)

    @admin.display(description="Uploaded Image Preview")
    def image_preview(self, obj: ForumPost):
        if not obj.image:
            return "No image attached."
        return format_html('<img src="{}" style="max-height: 250px; border-radius: 6px;" />', obj.image.url)


@admin.register(MessageConsent)
class MessageConsentAdmin(admin.ModelAdmin):
    list_display = ("requester", "recipient", "status", "updated_at")
    list_filter = ("status", "updated_at")
    search_fields = ("requester__username", "recipient__username")


@admin.register(DirectMessage)
class DirectMessageAdmin(admin.ModelAdmin):
    list_display = ("sender", "recipient", "sent_at", "is_read")
    list_filter = ("is_read", "sent_at")
    search_fields = ("sender__username", "recipient__username", "body")