from django.contrib.auth import views as auth_views
from django.urls import path
from . import views

urlpatterns = [
    # Public Splash Page & Vetting
    path("", views.splash_page_view, name="splash_page"),
    path("apply/", views.apply_options_view, name="apply_options"),
    path("apply/thank-you/", views.vetting_thank_you_view, name="vetting_thank_you"),
    path("apply/references/", views.reference_application_view, name="reference_apply"),
    path("apply/<str:role>/", views.vetting_application_view, name="vetting_apply"),

    # Authentication, Onboarding & Account Deletion
    path(
        "login/",
        auth_views.LoginView.as_view(
            template_name="accounts/login.html",
            redirect_authenticated_user=True,
        ),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(next_page="login"), name="logout"),
    path("account/change-password/", views.force_password_change_view, name="force_password_change"),
    path("account/profile/", views.profile_update_view, name="profile_update"),
    path("account/delete/", views.delete_own_account_view, name="delete_own_account"),

    # Member Directory, Member Profiles, Consent & Direct Messaging
    path("members/", views.member_directory_view, name="member_directory"),
    path("members/<int:member_pk>/", views.member_detail_view, name="member_detail"),
    path("members/<int:member_pk>/delete/", views.admin_delete_member_view, name="admin_delete_member"),
    path("consent/request/<int:recipient_pk>/", views.request_consent_view, name="request_consent"),
    path("consent/update/<int:consent_pk>/<str:action>/", views.update_consent_view, name="update_consent"),
    path("messages/<int:other_member_pk>/", views.conversation_view, name="conversation"),

    # Events & RSVPs
    path("events/", views.event_list_view, name="event_list"),
    path("events/<int:event_pk>/rsvp/", views.toggle_rsvp_view, name="toggle_rsvp"),

    # Forums
    path("forums/", views.forum_topic_list_view, name="forum_topic_list"),
    path("forums/<int:topic_pk>/", views.forum_topic_detail_view, name="forum_topic_detail"),
    path("forums/posts/<int:post_pk>/delete/", views.delete_forum_post_view, name="delete_forum_post"),
]