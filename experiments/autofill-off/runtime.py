"""Suppress built-in Android web-form Autofill without changing stored data.

Chromium's Android platform service uses AndroidAutofillClient/AndroidAutofillManager;
the ordinary fallback uses the browser clients and BrowserAutofillManager below.
Keep those fallback objects alive for their non-filling consumers.
"""

from pathlib import Path

BROWSER_MANAGER = "components/autofill/core/browser/foundations/browser_autofill_manager.cc"
AUTOFILL_CLIENT = "chrome/browser/ui/autofill/chrome_autofill_client.cc"
PAYMENTS_CLIENT = "chrome/browser/ui/autofill/payments/chrome_payments_autofill_client.cc"
MANUAL_ACCESSORY = "chrome/browser/keyboard_accessory/android/manual_filling_controller_impl.cc"
PASSWORD_CLIENT = "chrome/browser/password_manager/chrome_password_manager_client.cc"

MARKER = "SANDIUM_NO_INTERNAL_ANDROID_AUTOFILL"
GUARD = """
#if BUILDFLAG(IS_ANDROID)
  // SANDIUM_NO_INTERNAL_ANDROID_AUTOFILL: Keep client/data objects intact.
  {statement}
#endif
"""

# Match each full signature, not a possibly overloaded name or earlier callsite.
PATCHES = {
    BROWSER_MANAGER: (
        ("""void BrowserAutofillManager::OnFormSubmittedImpl(const FormData& form,
                                                 SubmissionSource source) {""", "return;"),
        ("""void BrowserAutofillManager::OnAskForValuesToFillImpl(
    const FormData& form,
    const FieldGlobalId& field_id,
    const gfx::Rect& caret_bounds,
    AutofillSuggestionTriggerSource trigger_source,
    std::optional<PasswordSuggestionRequest> password_request,
    base::ScopedClosureRunner scoped_on_after) {""", "return;"),
        ("""void BrowserAutofillManager::FillOrPreviewForm(
    mojom::ActionPersistence action_persistence,
    const FormGlobalId& form_id,
    const FieldGlobalId& trigger_field_id,
    const FillingPayload& filling_payload,
    AutofillTriggerSource trigger_source,
    const base::flat_set<FieldGlobalId>& blocked_fields) {""", "return;"),
        ("""void BrowserAutofillManager::FillOrPreviewField(
    mojom::ActionPersistence action_persistence,
    mojom::FieldActionType action_type,
    const FormGlobalId& form_id,
    const FieldGlobalId& field_id,
    const std::u16string& value,
    FillingProduct filling_product,
    std::optional<FieldType> field_type_used) {""", "return;"),
        ("""void BrowserAutofillManager::FillOrPreviewCreditCardForm(
    mojom::ActionPersistence action_persistence,
    const FormStructure& form,
    const AutofillField& trigger_field,
    const CreditCard& credit_card,
    AutofillTriggerSource trigger_source,
    const base::flat_set<FieldGlobalId>& blocked_fields) {""", "return;"),
        ("void BrowserAutofillManager::RequestRefillImpl(const FillId& fill_id) {", "return;"),
    ),
    AUTOFILL_CLIENT: (
        ("bool ChromeAutofillClient::IsAutofillEnabled() const {", "return false;"),
        ("bool ChromeAutofillClient::IsAutofillProfileEnabled() const {", "return false;"),
        ("bool ChromeAutofillClient::IsAutocompleteEnabled() const {", "return false;"),
    ),
    PAYMENTS_CLIENT: (
        ("bool ChromePaymentsAutofillClient::IsAutofillPaymentMethodsEnabled() const {",
         "return false;"),
    ),
    # All built-in address/payment/password accessory selection dispatches
    # pass this native Android controller. Its separate passkey route is intact.
    MANUAL_ACCESSORY: (
        ("""bool ManualFillingControllerImpl::ShouldShowAccessoryForLastFocusedFieldType()
    const {""", "return false;"),
        ("""void ManualFillingControllerImpl::OnFillingTriggered(
    AccessoryTabType type,
    const autofill::AccessorySheetField& selection) {""", "return;"),
    ),
    PASSWORD_CLIENT: (
        ("""bool ChromePasswordManagerClient::IsFillingEnabled(
    const url::Origin& origin,
    base::optional_ref<const GURL> url) const {""", "return false;"),
        ("""void ChromePasswordManagerClient::AutofillHttpAuth(
    const PasswordForm& preferred_match,
    const password_manager::PasswordFormManagerForUI* form_manager) {""", "return;"),
        # On Android this method normally raises the in-browser keyboard accessory
        # and manual password generation, bypassing IsFillingEnabled.
        ("""void ChromePasswordManagerClient::FocusedInputChanged(
    PasswordManagerDriver* driver,
    autofill::FieldRendererId focused_field_id,
    autofill::mojom::FocusedFieldType focused_field_type) {""", "return;"),
    ),
}


def transform(path: str, source: str) -> str:
    edits = PATCHES[path]
    replay = MARKER in source
    if replay and source.count(MARKER) != len(edits):
        raise SystemExit(f"partial Sandium Autofill runtime overlay: {path}")
    if path == MANUAL_ACCESSORY:
        anchor = '#include "base/trace_event/trace_event.h"'
        include = '#include "build/build_config.h"'
        replacement = anchor + "\n" + include
        if replay:
            if source.count(replacement) != 1:
                raise SystemExit(f"missing Sandium Autofill build config: {path}")
        else:
            if source.count(anchor) != 1 or include in source:
                raise SystemExit(f"unexpected Sandium Autofill build config: {path}")
            source = source.replace(anchor, replacement, 1)
    for anchor, statement in edits:
        replacement = anchor + GUARD.format(statement=statement).rstrip("\n")
        needle = replacement if replay else anchor
        if source.count(needle) != 1:
            raise SystemExit(f"expected exactly one Autofill runtime anchor in {path}: {anchor}")
        if not replay:
            source = source.replace(anchor, replacement, 1)
    return source


def plan(root: Path) -> dict[Path, str]:
    return {root / path: transform(path, (root / path).read_text()) for path in PATCHES}
