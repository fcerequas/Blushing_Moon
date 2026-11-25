from dataclasses import dataclass
from django import forms
from django.core.exceptions import ValidationError
from .models import (
    DirectMessage,
    ForumPost,
    Member,
    MessageConsent,
    RoleChoices,
    VettingApplication,
)


@dataclass(frozen=True)
class VettingQuestion:
    key: str
    label: str
    help_text: str = ""
    rows: int = 3


COMMON_OPENING_QUESTIONS: list[VettingQuestion] = [
    VettingQuestion(
        key="q1_history_and_style",
        label="1. Tell me a bit about the history of your interest in spanking and your style of play.",
        rows=4,
    ),
    VettingQuestion(
        key="q2_consent_understanding",
        label="2. Describe your understanding of Consent in a spanking scene.",
        rows=4,
    ),
]


def build_top_scenarios(question_num: int, as_role_suffix: str = "") -> list[VettingQuestion]:
    header = f"How would you respond to each of the following scenarios{as_role_suffix}?"
    return [
        VettingQuestion(
            key=f"q{question_num}a_top_red",
            label=f"{question_num}a. Your play partner says ‘Red’?",
            help_text=header,
            rows=2,
        ),
        VettingQuestion(
            key=f"q{question_num}b_top_yellow",
            label=f"{question_num}b. Your play partner says ‘Yellow’?",
            rows=2,
        ),
        VettingQuestion(
            key=f"q{question_num}c_top_presumed_objection",
            label=f"{question_num}c. Your play partner objects to something you presumed in negotiation.",
            rows=3,
        ),
        VettingQuestion(
            key=f"q{question_num}d_top_withdrawn_consent",
            label=f"{question_num}d. Your play partner withdraws consent for something included in negotiations.",
            rows=3,
        ),
    ]


def build_bottom_scenarios(question_num: int, as_role_suffix: str = "") -> list[VettingQuestion]:
    header = f"How would you respond to each of the following scenarios{as_role_suffix}?"
    return [
        VettingQuestion(
            key=f"q{question_num}a_bottom_uncomfortable_intensity",
            label=f"{question_num}a. The intensity of the play is becoming uncomfortable.",
            help_text=header,
            rows=2,
        ),
        VettingQuestion(
            key=f"q{question_num}b_bottom_stop_immediately",
            label=f"{question_num}b. You want your play partner to stop immediately.",
            rows=2,
        ),
        VettingQuestion(
            key=f"q{question_num}c_bottom_minor_unnegotiated",
            label=(
                f"{question_num}c. Your play partner does something (minor) without asking, "
                "that you did not explicitly negotiate. Minor meaning that you don’t want "
                "to end the scene, but you want them to stop."
            ),
            rows=3,
        ),
        VettingQuestion(
            key=f"q{question_num}d_bottom_negotiated_boundary_violated",
            label=f"{question_num}d. Your play partner violates a boundary established during negotiation.",
            rows=3,
        ),
        VettingQuestion(
            key=f"q{question_num}e_bottom_unnegotiated_boundary_violated",
            label=(
                f"{question_num}e. Your play partner violates a boundary which was not "
                "discussed, but which falls outside of a reasonable misunderstanding."
            ),
            rows=3,
        ),
        VettingQuestion(
            key=f"q{question_num}f_bottom_general_discomfort",
            label=f"{question_num}f. You’re uncomfortable with something that your play partner does, negotiated or not.",
            rows=3,
        ),
    ]


VETTING_QUESTIONS_BY_ROLE: dict[str, list[VettingQuestion]] = {
    RoleChoices.TOP: [
        *COMMON_OPENING_QUESTIONS,
        VettingQuestion(
            key="q3_negotiate_general",
            label="3. Do you generally negotiate before a scene?",
            rows=2,
        ),
        VettingQuestion(
            key="q3a_questions_asked",
            label="3a. If so, what questions do you ask?",
            rows=3,
        ),
        VettingQuestion(
            key="q3b_assumed_in_bounds",
            label=(
                "3b. In either case, are there elements that you assume are in bounds "
                "based on someone agreeing to play?"
            ),
            help_text=(
                "Please note: This is not a trick question, negotiating everything "
                "would be time consuming. I’m just interested in where you draw the line."
            ),
            rows=3,
        ),
        *build_top_scenarios(question_num=4),
    ],
    RoleChoices.BOTTOM: [
        *COMMON_OPENING_QUESTIONS,
        VettingQuestion(
            key="q3_insist_negotiation",
            label="3. Do you insist on negotiation before a scene?",
            rows=2,
        ),
        VettingQuestion(
            key="q3a_primary_concerns",
            label="3a. If so, what are your primary concerns?",
            rows=3,
        ),
        VettingQuestion(
            key="q3b_assumed_in_bounds",
            label=(
                "3b. In either case, are there elements that you assume are in bounds "
                "(e.g. hand spanking, lifting a skirt, etc.)?"
            ),
            rows=3,
        ),
        *build_bottom_scenarios(question_num=4),
    ],
    RoleChoices.SWITCH: [
        *COMMON_OPENING_QUESTIONS,
        VettingQuestion(
            key="q3_negotiate_general",
            label="3. Do you generally negotiate before a scene?",
            rows=2,
        ),
        VettingQuestion(
            key="q3a_differs_by_role",
            label="3a. Is the answer different depending on whether you're topping or bottoming?",
            rows=2,
        ),
        VettingQuestion(
            key="q3b_questions_asked",
            label="3b. If so, what questions do you ask?",
            rows=3,
        ),
        VettingQuestion(
            key="q3c_assumed_in_bounds",
            label=(
                "3c. In either case, are there elements that you assume are in bounds "
                "based on someone agreeing to play?"
            ),
            help_text=(
                "Please note: This is not a trick question, negotiating everything "
                "would be time consuming. I’m just interested in where you draw the line."
            ),
            rows=3,
        ),
        *build_top_scenarios(question_num=4, as_role_suffix=" as a top"),
        *build_bottom_scenarios(question_num=5, as_role_suffix=" as a bottom"),
    ],
}


APPLICANT_IDENTITY_FIELDS = ["rl_name", "fetlife_name", "applicant_name", "email"]
APPLICANT_IDENTITY_LABELS = {
    "rl_name": "RL Name",
    "fetlife_name": "Fet Life Profile Name",
    "applicant_name": "Your Preferred Name or Scene Alias",
    "email": "Email Address (Used to send your login or interview request)",
}


class VettingApplicationForm(forms.ModelForm):
    class Meta:
        model = VettingApplication
        fields = APPLICANT_IDENTITY_FIELDS
        labels = APPLICANT_IDENTITY_LABELS

    def __init__(self, *args, role: str, **kwargs):
        self.role = role
        super().__init__(*args, **kwargs)

        self.role_questions = VETTING_QUESTIONS_BY_ROLE.get(self.role, [])

        for q in self.role_questions:
            self.fields[q.key] = forms.CharField(
                label=q.label,
                help_text=q.help_text,
                required=True,
                widget=forms.Textarea(
                    attrs={
                        "rows": q.rows,
                        "placeholder": "Provide a complete, honest response...",
                    }
                ),
            )

        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")

    def clean_email(self) -> str:
        email = self.cleaned_data["email"].lower().strip()
        if Member.objects.filter(email__iexact=email).exists():
            raise ValidationError(
                "An active Blushing Moon member account with this email already exists. Please log in instead."
            )
        return email

    def save(self, commit: bool = True) -> VettingApplication:
        instance: VettingApplication = super().save(commit=False)
        instance.role = self.role
        instance.is_reference = False
        instance.vetting_answers = {
            q.label: self.cleaned_data[q.key].strip()
            for q in self.role_questions
        }
        if commit:
            instance.save()
        return instance


class ReferenceApplicationForm(forms.ModelForm):
    REFERENCES_LABEL = (
        "References (Either RL or Fet name is acceptable; an email is appreciated "
        "but not necessary if the person is reachable through Fet)."
    )

    references = forms.CharField(
        label=REFERENCES_LABEL,
        required=True,
        widget=forms.Textarea(
            attrs={
                "rows": 5,
                "placeholder": "List your scene or member references here...",
            }
        ),
    )

    class Meta:
        model = VettingApplication
        fields = APPLICANT_IDENTITY_FIELDS
        labels = APPLICANT_IDENTITY_LABELS

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")

    def clean_email(self) -> str:
        email = self.cleaned_data["email"].lower().strip()
        if Member.objects.filter(email__iexact=email).exists():
            raise ValidationError(
                "An active Blushing Moon member account with this email already exists. Please log in instead."
            )
        return email

    def save(self, commit: bool = True) -> VettingApplication:
        instance: VettingApplication = super().save(commit=False)
        instance.role = ""
        instance.is_reference = True
        instance.vetting_answers = {
            self.REFERENCES_LABEL: self.cleaned_data["references"].strip()
        }
        if commit:
            instance.save()
        return instance


class MemberProfileForm(forms.ModelForm):
    MAX_IMAGE_MB = 5

    class Meta:
        model = Member
        fields = ["profile_picture", "username", "first_name", "last_name", "email", "role", "bio"]
        labels = {
            "profile_picture": "Profile Picture (Optional, max 5 MB)",
            "first_name": "Preferred Name / Alias",
            "role": "Club Role (Top / Bottom / Switch)",
            "bio": "About Me / Profile Notes",
        }
        widgets = {
            "profile_picture": forms.ClearableFileInput(attrs={"accept": "image/*"}),
            "bio": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.Select):
                field.widget.attrs.setdefault("class", "form-select")
            else:
                field.widget.attrs.setdefault("class", "form-control")

    def clean_profile_picture(self):
        image = self.cleaned_data.get("profile_picture")
        if image and hasattr(image, "size") and image.size > self.MAX_IMAGE_MB * 1024 * 1024:
            raise ValidationError(f"Profile picture must be under {self.MAX_IMAGE_MB} MB.")
        return image


class DirectMessageForm(forms.ModelForm):
    class Meta:
        model = DirectMessage
        fields = ["body"]
        widgets = {
            "body": forms.Textarea(
                attrs={
                    "rows": 3,
                    "class": "form-control",
                    "placeholder": "Type your message here...",
                }
            )
        }
        labels = {"body": ""}

    def __init__(self, *args, sender, recipient, **kwargs):
        self.sender = sender
        self.recipient = recipient
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        if not MessageConsent.has_active_consent(self.sender, self.recipient):
            raise ValidationError(
                "You do not have active consent to message this member, or consent has been revoked."
            )
        return cleaned_data

    def save(self, commit: bool = True) -> DirectMessage:
        instance = super().save(commit=False)
        instance.sender = self.sender
        instance.recipient = self.recipient
        if commit:
            instance.save()
        return instance


class ForumPostForm(forms.ModelForm):
    MAX_IMAGE_MB = 5

    class Meta:
        model = ForumPost
        fields = ["body", "image"]
        widgets = {
            "body": forms.Textarea(
                attrs={
                    "rows": 3,
                    "class": "form-control",
                    "placeholder": "Write your reply (or add a caption for an image)...",
                }
            ),
            "image": forms.ClearableFileInput(
                attrs={
                    "class": "form-control",
                    "accept": "image/*",
                }
            ),
        }
        labels = {
            "body": "",
            "image": "Attach an Image (Optional, max 5 MB)",
        }

    def clean_image(self):
        image = self.cleaned_data.get("image")
        if image and image.size > self.MAX_IMAGE_MB * 1024 * 1024:
            raise ValidationError(f"Image file size must be under {self.MAX_IMAGE_MB} MB.")
        return image

    def clean(self):
        cleaned_data = super().clean()
        body = (cleaned_data.get("body") or "").strip()
        image = cleaned_data.get("image")
        if not body and not image:
            raise ValidationError("Please enter a message or attach an image before posting.")
        return cleaned_data