from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.core.mail import send_mail
from django.db.models import Q
from django.http import Http404, HttpRequest, HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .forms import (
    DirectMessageForm,
    ForumPostForm,
    MemberProfileForm,
    ReferenceApplicationForm,
    VettingApplicationForm,
)
from .models import (
    DirectMessage,
    Event,
    ForumPost,
    ForumTopic,
    Member,
    MessageConsent,
    RoleChoices,
    RSVP,
)


# ---------------------------------------------------------------------------
# PUBLIC SPLASH PAGE & VETTING WORKFLOW
# ---------------------------------------------------------------------------
def splash_page_view(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect("profile_update")

    return render(request, "public/splash.html")


def apply_options_view(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect("profile_update")

    return render(request, "public/apply_options.html")


def reference_application_view(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = ReferenceApplicationForm(request.POST)
        if form.is_valid():
            application = form.save()
            admin_review_url = request.build_absolute_uri(
                reverse("admin:bmclub_vettingapplication_change", args=[application.pk])
            )
            send_mail(
                subject=f"[New Reference Application] {application.applicant_name}",
                message=(
                    f"A new applicant has submitted a reference application.\n\n"
                    f"RL Name: {application.rl_name}\n"
                    f"FetLife Profile: {application.fetlife_name}\n"
                    f"Preferred Name / Alias: {application.applicant_name}\n"
                    f"Email: {application.email}\n\n"
                    f"Review and Approve/Reject in the Admin Panel:\n{admin_review_url}"
                ),
                from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@blushingmoon.local"),
                recipient_list=[getattr(settings, "DEFAULT_FROM_EMAIL", "admin@blushingmoon.local")],
                fail_silently=True,
            )
            return redirect("vetting_thank_you")
    else:
        form = ReferenceApplicationForm()

    return render(
        request,
        "public/vetting_form.html",
        {
            "form": form,
            "page_title": "Apply with References",
        },
    )


def vetting_application_view(request: HttpRequest, role: str) -> HttpResponse:
    normalized_role = role.upper()
    if normalized_role not in RoleChoices.values:
        raise Http404(f"Invalid application role: {role}")

    role_label = RoleChoices(normalized_role).label

    if request.method == "POST":
        form = VettingApplicationForm(request.POST, role=normalized_role)
        if form.is_valid():
            application = form.save()
            admin_review_url = request.build_absolute_uri(
                reverse("admin:bmclub_vettingapplication_change", args=[application.pk])
            )
            send_mail(
                subject=f"[New Vetting Application] {application.applicant_name} ({role_label})",
                message=(
                    f"A new applicant has submitted a vetting questionnaire.\n\n"
                    f"RL Name: {application.rl_name}\n"
                    f"FetLife Profile: {application.fetlife_name}\n"
                    f"Preferred Name / Alias: {application.applicant_name}\n"
                    f"Email: {application.email}\n"
                    f"Selected Role: {role_label}\n\n"
                    f"Review and Approve/Reject in the Admin Panel:\n{admin_review_url}"
                ),
                from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@blushingmoon.local"),
                recipient_list=[getattr(settings, "DEFAULT_FROM_EMAIL", "admin@blushingmoon.local")],
                fail_silently=True,
            )
            return redirect("vetting_thank_you")
    else:
        form = VettingApplicationForm(role=normalized_role)

    return render(
        request,
        "public/vetting_form.html",
        {
            "form": form,
            "page_title": f"Vetting Application — {role_label}",
        },
    )


def vetting_thank_you_view(request: HttpRequest) -> HttpResponse:
    return render(request, "public/vetting_thank_you.html")


# ---------------------------------------------------------------------------
# MEMBER ONBOARDING, PROFILE MANAGEMENT & ACCOUNT DELETION
# ---------------------------------------------------------------------------
@login_required
def force_password_change_view(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = PasswordChangeForm(user=request.user, data=request.POST)
        if form.is_valid():
            user = form.save()
            user.must_change_password = False
            user.save(update_fields=["must_change_password"])
            update_session_auth_hash(request, user)
            messages.success(request, "Your password has been updated! Please review your profile.")
            return redirect("profile_update")
    else:
        form = PasswordChangeForm(user=request.user)

    for field in form.fields.values():
        field.widget.attrs.setdefault("class", "form-control")

    return render(request, "accounts/force_password_change.html", {"form": form})


@login_required
def profile_update_view(request: HttpRequest) -> HttpResponse:
    old_picture = request.user.profile_picture.name if request.user.profile_picture else None

    if request.method == "POST":
        form = MemberProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            updated_user = form.save()
            new_picture = updated_user.profile_picture.name if updated_user.profile_picture else None
            if old_picture and old_picture != new_picture:
                updated_user.profile_picture.storage.delete(old_picture)
            messages.success(request, "Your member profile has been saved.")
            return redirect("profile_update")
    else:
        form = MemberProfileForm(instance=request.user)

    return render(request, "accounts/profile_update.html", {"form": form})


@login_required
def delete_own_account_view(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        if request.user.is_superuser:
            messages.error(request, "Superuser accounts cannot be self-deleted from the profile page.")
            return redirect("profile_update")

        user = request.user
        if user.profile_picture:
            user.profile_picture.delete(save=False)
        logout(request)
        user.delete()
        messages.info(request, "Your membership account has been permanently deleted.")
        return redirect("splash_page")

    return redirect("profile_update")


@login_required
def admin_delete_member_view(request: HttpRequest, member_pk: int) -> HttpResponse:
    if not request.user.is_staff:
        return HttpResponseForbidden("Only administrators can delete member accounts.")

    if request.method == "POST":
        member = get_object_or_404(Member, pk=member_pk)
        if member == request.user:
            messages.error(request, "You cannot delete your own administrator account.")
        elif member.is_superuser and not request.user.is_superuser:
            messages.error(request, "Only a superuser can delete another superuser.")
        else:
            username = member.username
            if member.profile_picture:
                member.profile_picture.delete(save=False)
            member.delete()
            messages.warning(
                request,
                f"Member '{username}' and all associated records have been permanently deleted.",
            )

    return redirect("member_directory")


# ---------------------------------------------------------------------------
# MEMBER DIRECTORY, MEMBER PROFILES, CONSENT & DIRECT MESSAGING
# ---------------------------------------------------------------------------
@login_required
def member_directory_view(request: HttpRequest) -> HttpResponse:
    members = Member.objects.filter(is_active=True).exclude(pk=request.user.pk)
    consents = MessageConsent.objects.filter(Q(requester=request.user) | Q(recipient=request.user))

    consent_map = {}
    for c in consents:
        other_user = c.recipient if c.requester == request.user else c.requester
        consent_map[other_user.pk] = {
            "id": c.pk,
            "status": c.status,
            "is_requester": c.requester == request.user,
        }

    member_data = [{"member": m, "consent": consent_map.get(m.pk, None)} for m in members]
    return render(request, "messaging/directory.html", {"member_data": member_data})


@login_required
def member_detail_view(request: HttpRequest, member_pk: int) -> HttpResponse:
    """Displays another member's profile with their profile picture in the upper right."""
    if member_pk == request.user.pk:
        return redirect("profile_update")

    member = get_object_or_404(Member, pk=member_pk, is_active=True)
    consent_obj = MessageConsent.objects.filter(
        Q(requester=request.user, recipient=member) | Q(requester=member, recipient=request.user)
    ).first()

    consent_info = None
    if consent_obj:
        consent_info = {
            "id": consent_obj.pk,
            "status": consent_obj.status,
            "is_requester": consent_obj.requester == request.user,
        }

    return render(
        request,
        "messaging/member_detail.html",
        {
            "member": member,
            "consent": consent_info,
        },
    )


@login_required
def request_consent_view(request: HttpRequest, recipient_pk: int) -> HttpResponse:
    recipient = get_object_or_404(Member, pk=recipient_pk, is_active=True)
    if recipient == request.user:
        messages.error(request, "You cannot request consent to message yourself.")
        return redirect("member_directory")

    existing_consent = MessageConsent.objects.filter(
        Q(requester=request.user, recipient=recipient) | Q(requester=recipient, recipient=request.user)
    ).first()

    if existing_consent:
        if existing_consent.status == MessageConsent.Status.REVOKED:
            existing_consent.requester = request.user
            existing_consent.recipient = recipient
            existing_consent.status = MessageConsent.Status.PENDING
            existing_consent.save(update_fields=["requester", "recipient", "status", "updated_at"])
            messages.success(request, f"New consent request sent to {recipient.username}.")
        else:
            messages.info(request, "A consent request or active relationship already exists.")
    else:
        MessageConsent.objects.create(
            requester=request.user,
            recipient=recipient,
            status=MessageConsent.Status.PENDING,
        )
        messages.success(request, f"Consent request sent to {recipient.username}.")

    return redirect("member_directory")


@login_required
def update_consent_view(request: HttpRequest, consent_pk: int, action: str) -> HttpResponse:
    consent = get_object_or_404(MessageConsent, pk=consent_pk)
    if request.user not in (consent.requester, consent.recipient):
        return HttpResponseForbidden("Permission denied.")

    if action == "accept" and request.user == consent.recipient and consent.status == MessageConsent.Status.PENDING:
        consent.status = MessageConsent.Status.ACCEPTED
        consent.save(update_fields=["status", "updated_at"])
        messages.success(request, f"Accepted messaging consent with {consent.requester.username}.")
    elif action == "revoke":
        consent.revoke()
        messages.warning(request, "Messaging consent has been revoked.")

    return redirect("member_directory")


@login_required
def conversation_view(request: HttpRequest, other_member_pk: int) -> HttpResponse:
    other_member = get_object_or_404(Member, pk=other_member_pk)
    if not MessageConsent.has_active_consent(request.user, other_member):
        messages.error(request, "Active consent is required to view or send direct messages.")
        return redirect("member_directory")

    messages_list = DirectMessage.objects.filter(
        Q(sender=request.user, recipient=other_member) | Q(sender=other_member, recipient=request.user)
    ).order_by("sent_at")

    DirectMessage.objects.filter(sender=other_member, recipient=request.user, is_read=False).update(is_read=True)

    if request.method == "POST":
        form = DirectMessageForm(request.POST, sender=request.user, recipient=other_member)
        if form.is_valid():
            form.save()
            return redirect("conversation", other_member_pk=other_member.pk)
    else:
        form = DirectMessageForm(sender=request.user, recipient=other_member)

    return render(
        request,
        "messaging/conversation.html",
        {"other_member": other_member, "messages_list": messages_list, "form": form},
    )


# ---------------------------------------------------------------------------
# EVENTS & FORUMS
# ---------------------------------------------------------------------------
@login_required
def event_list_view(request: HttpRequest) -> HttpResponse:
    events = Event.objects.filter(is_rsvp_open=True).order_by("event_date")
    user_rsvps = set(RSVP.objects.filter(member=request.user, attending=True).values_list("event_id", flat=True))
    return render(request, "events/event_list.html", {"events": events, "user_rsvps": user_rsvps})


@login_required
def toggle_rsvp_view(request: HttpRequest, event_pk: int) -> HttpResponse:
    event = get_object_or_404(Event, pk=event_pk, is_rsvp_open=True)
    rsvp, _ = RSVP.objects.get_or_create(event=event, member=request.user)
    rsvp.attending = not rsvp.attending
    rsvp.save(update_fields=["attending", "updated_at"])
    messages.success(request, f"RSVP updated for {event.title}.")
    return redirect("event_list")


@login_required
def forum_topic_list_view(request: HttpRequest) -> HttpResponse:
    topics = ForumTopic.objects.all().order_by("-created_at")
    return render(request, "forums/topic_list.html", {"topics": topics})


@login_required
def forum_topic_detail_view(request: HttpRequest, topic_pk: int) -> HttpResponse:
    topic = get_object_or_404(ForumTopic, pk=topic_pk)
    posts = topic.posts.select_related("author").all()

    if request.method == "POST":
        form = ForumPostForm(request.POST, request.FILES)
        if form.is_valid():
            post = form.save(commit=False)
            post.topic = topic
            post.author = request.user
            post.save()
            messages.success(request, "Your post has been published.")
            return redirect("forum_topic_detail", topic_pk=topic.pk)
    else:
        form = ForumPostForm()

    return render(request, "forums/topic_detail.html", {"topic": topic, "posts": posts, "form": form})


@login_required
def delete_forum_post_view(request: HttpRequest, post_pk: int) -> HttpResponse:
    post = get_object_or_404(ForumPost, pk=post_pk)
    topic_pk = post.topic.pk
    if request.user.is_staff or post.author == request.user:
        if post.image:
            post.image.delete(save=False)
        post.delete()
        messages.warning(request, "Forum post deleted.")
    else:
        return HttpResponseForbidden("Permission denied.")
    return redirect("forum_topic_detail", topic_pk=topic_pk)