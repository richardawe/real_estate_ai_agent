/**
 * Intake form logic.
 *
 * Renders a multi-step form, verifies GitHub auth,
 * and submits via repository_dispatch when complete.
 */

import { gh } from '../js/github-client.js';
import { CONFIG } from '../config.js';
import { requireAuth } from '../js/auth.js';

// Require authentication before showing the form — redirects to /login/ if not signed in.
await requireAuth();

const params = new URLSearchParams(location.search);
const WORKFLOW_TYPE = params.get('type') === 'rent' ? 'rent' : 'buy';

document.getElementById('workflow-type-label').textContent =
  WORKFLOW_TYPE === 'buy' ? 'Buy workflow' : 'Rent workflow';

// ---------------------------------------------------------------------------
// Step definitions
// ---------------------------------------------------------------------------

const BUY_STEPS = [
  {
    title: "Your contact details",
    fields: [
      { id: "full_name",  label: "Full name",    type: "text",  required: true },
      { id: "email",      label: "Email",         type: "email", required: true },
      { id: "phone",      label: "Phone (optional)", type: "tel", required: false },
    ],
  },
  {
    title: "Property requirements",
    fields: [
      { id: "locations",     label: "Preferred locations (comma-separated)", type: "text",   required: true },
      { id: "budget_min",    label: "Minimum budget (£)",                    type: "number", required: true },
      { id: "budget_max",    label: "Maximum budget (£)",                    type: "number", required: true },
      { id: "bedrooms_min",  label: "Minimum bedrooms",                      type: "number", required: true },
      { id: "property_types",label: "Property types (e.g. house, flat)",     type: "text",   required: false },
    ],
  },
  {
    title: "Must-haves and preferences",
    fields: [
      { id: "must_haves",    label: "Must-haves (e.g. garden, parking)",     type: "text", required: false },
      { id: "nice_to_haves", label: "Nice-to-haves",                         type: "text", required: false },
      { id: "move_in_by",    label: "Move-in by (optional)",                 type: "date", required: false },
    ],
  },
  {
    title: "Financial details",
    fields: [
      { id: "gross_monthly_income", label: "Gross monthly income (£, optional)", type: "number", required: false },
      { id: "deposit_available",    label: "Deposit available (£, optional)",    type: "number", required: false },
      { id: "first_time_buyer",     label: "First-time buyer?",                  type: "checkbox", required: false },
    ],
  },
];

const RENT_STEPS = [
  {
    title: "Your contact details",
    fields: [
      { id: "full_name", label: "Full name",        type: "text",  required: true },
      { id: "email",     label: "Email",             type: "email", required: true },
      { id: "phone",     label: "Phone (optional)",  type: "tel",   required: false },
    ],
  },
  {
    title: "Property requirements",
    fields: [
      { id: "locations",    label: "Preferred locations (comma-separated)", type: "text",   required: true },
      { id: "rent_max",     label: "Maximum monthly rent (£)",              type: "number", required: true },
      { id: "bedrooms_min", label: "Minimum bedrooms",                      type: "number", required: true },
      { id: "move_in_by",   label: "Move-in by (optional)",                 type: "date",   required: false },
    ],
  },
  {
    title: "Preferences",
    fields: [
      { id: "must_haves",           label: "Must-haves (e.g. parking)",  type: "text",   required: false },
      { id: "furnished_preference", label: "Furnished preference",       type: "select",
        options: ["", "furnished", "unfurnished", "either"],
        required: false },
      { id: "pets",                 label: "Pets?",                      type: "checkbox", required: false },
      { id: "gross_monthly_income", label: "Gross monthly income (£, optional)", type: "number", required: false },
    ],
  },
];

const STEPS = WORKFLOW_TYPE === 'buy' ? BUY_STEPS : RENT_STEPS;

// ---------------------------------------------------------------------------
// Render steps
// ---------------------------------------------------------------------------

const stepsContainer = document.getElementById('steps');
const prevBtn = document.getElementById('prev-btn');
const nextBtn = document.getElementById('next-btn');
const submitBtn = document.getElementById('submit-btn');
let currentStep = 0;

function renderSteps() {
  stepsContainer.innerHTML = '';

  // Step indicator
  const indicator = document.createElement('div');
  indicator.className = 'step-indicator';
  STEPS.forEach((_, i) => {
    const dot = document.createElement('div');
    dot.className = 'step-dot' + (i < currentStep ? ' done' : i === currentStep ? ' active' : '');
    indicator.appendChild(dot);
  });
  stepsContainer.appendChild(indicator);

  // Current step fields
  const step = STEPS[currentStep];
  const heading = document.createElement('h2');
  heading.textContent = step.title;
  heading.style.marginBottom = '1.25rem';
  stepsContainer.appendChild(heading);

  for (const field of step.fields) {
    const group = document.createElement('div');
    group.className = 'form-group';

    const label = document.createElement('label');
    label.setAttribute('for', field.id);
    label.textContent = field.label;
    group.appendChild(label);

    let input;
    if (field.type === 'select') {
      input = document.createElement('select');
      for (const opt of (field.options || [])) {
        const o = document.createElement('option');
        o.value = opt;
        o.textContent = opt || '— choose —';
        input.appendChild(o);
      }
    } else {
      input = document.createElement('input');
      input.type = field.type;
      if (field.type === 'checkbox') {
        input.style.width = 'auto';
      }
    }

    input.id = field.id;
    input.name = field.id;
    if (field.required) input.required = true;

    // Restore saved value
    const saved = sessionStorage.getItem('intake_' + field.id);
    if (saved !== null) {
      if (field.type === 'checkbox') input.checked = saved === 'true';
      else input.value = saved;
    }

    group.appendChild(input);
    stepsContainer.appendChild(group);
  }

  // Nav buttons
  prevBtn.classList.toggle('hidden', currentStep === 0);
  nextBtn.classList.toggle('hidden', currentStep === STEPS.length - 1);
  submitBtn.classList.toggle('hidden', currentStep !== STEPS.length - 1);
}

function saveCurrentStep() {
  const step = STEPS[currentStep];
  for (const field of step.fields) {
    const el = document.getElementById(field.id);
    if (!el) continue;
    sessionStorage.setItem(
      'intake_' + field.id,
      field.type === 'checkbox' ? el.checked : el.value
    );
  }
}

function validateCurrentStep() {
  const step = STEPS[currentStep];
  for (const field of step.fields) {
    if (!field.required) continue;
    const el = document.getElementById(field.id);
    if (!el) continue;
    if (!el.value.trim()) {
      el.focus();
      return false;
    }
  }
  return true;
}

prevBtn.addEventListener('click', () => {
  saveCurrentStep();
  currentStep--;
  renderSteps();
});

nextBtn.addEventListener('click', () => {
  if (!validateCurrentStep()) return;
  saveCurrentStep();
  currentStep++;
  renderSteps();
});

// ---------------------------------------------------------------------------
// Show form — user is authenticated (requireAuth() would have redirected otherwise)
// ---------------------------------------------------------------------------

const authGate = document.getElementById('auth-gate');
const intakeForm = document.getElementById('intake-form');
const successMessage = document.getElementById('success-message');

// Hide the auth gate and show the form immediately since we are authenticated.
authGate.classList.add('hidden');
intakeForm.classList.remove('hidden');
renderSteps();

// ---------------------------------------------------------------------------
// Submit
// ---------------------------------------------------------------------------

intakeForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  saveCurrentStep();

  // Collect all field values into a readable paragraph for the LLM.
  const allFields = STEPS.flatMap(s => s.fields);
  const lines = [];
  for (const field of allFields) {
    const val = sessionStorage.getItem('intake_' + field.id);
    if (val && val !== 'false') {
      lines.push(`${field.label}: ${val}`);
    }
  }
  const intakeText = lines.join('\n');

  submitBtn.disabled = true;
  submitBtn.textContent = 'Submitting…';

  try {
    const issue = await gh.submitIntake({ workflowType: WORKFLOW_TYPE, intakeText });

    intakeForm.classList.add('hidden');
    successMessage.classList.remove('hidden');

    document.getElementById('workflow-link').href =
      `https://github.com/${CONFIG.GITHUB_REPO}/issues/${issue.number}`;
  } catch (err) {
    submitBtn.disabled = false;
    submitBtn.textContent = 'Submit →';
    const errorEl = document.getElementById('intake-error');
    if (errorEl) {
      errorEl.textContent = 'Submission failed: ' + err.message;
      errorEl.classList.remove('hidden');
    } else {
      // Fallback: log to console (no alert)
      console.error('Submission failed:', err.message);
    }
  }
});
