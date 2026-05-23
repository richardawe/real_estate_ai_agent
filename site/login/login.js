/**
 * Login / sign-up form handler.
 *
 * Handles tab switching, field validation, Supabase auth calls, and
 * post-auth redirect.  No alert() calls — all errors rendered inline.
 */

import { signIn, signUp, getSession } from '../js/auth.js';

// ---------------------------------------------------------------------------
// Redirect immediately if already signed in
// ---------------------------------------------------------------------------

const existingSession = await getSession();
if (existingSession) {
  location.href = sessionStorage.getItem('returnTo') || '/';
}

// ---------------------------------------------------------------------------
// Tab switching
// ---------------------------------------------------------------------------

const tabs = document.querySelectorAll('.auth-tab');
const panels = document.querySelectorAll('.auth-panel');

tabs.forEach(tab => {
  tab.addEventListener('click', () => {
    const target = tab.dataset.tab;
    tabs.forEach(t => t.classList.toggle('active', t.dataset.tab === target));
    panels.forEach(p => p.classList.toggle('active', p.id === `panel-${target}`));
  });
});

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function showError(elementId, message) {
  const el = document.getElementById(elementId);
  if (!el) return;
  el.textContent = message;
  el.classList.add('visible');
}

function hideError(elementId) {
  const el = document.getElementById(elementId);
  if (el) el.classList.remove('visible');
}

function setFieldError(inputEl, errorId, visible) {
  if (visible) {
    inputEl.classList.add('error');
    document.getElementById(errorId).classList.add('visible');
  } else {
    inputEl.classList.remove('error');
    document.getElementById(errorId).classList.remove('visible');
  }
}

function setSubmitting(btn, isSubmitting) {
  btn.disabled = isSubmitting;
  btn.textContent = isSubmitting ? 'Please wait…' : btn.dataset.label;
}

// Preserve original button labels for reset
document.getElementById('signin-btn').dataset.label = 'Sign in';
document.getElementById('signup-btn').dataset.label = 'Create account';

// ---------------------------------------------------------------------------
// Sign-in form
// ---------------------------------------------------------------------------

const signinForm = document.getElementById('form-signin');

signinForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  hideError('signin-error');

  const emailEl = document.getElementById('signin-email');
  const passwordEl = document.getElementById('signin-password');
  const btn = document.getElementById('signin-btn');

  // Client-side validation
  let valid = true;
  if (!emailEl.value.trim() || !emailEl.validity.valid) {
    setFieldError(emailEl, 'signin-email-error', true);
    valid = false;
  } else {
    setFieldError(emailEl, 'signin-email-error', false);
  }
  if (!passwordEl.value) {
    setFieldError(passwordEl, 'signin-password-error', true);
    valid = false;
  } else {
    setFieldError(passwordEl, 'signin-password-error', false);
  }
  if (!valid) return;

  setSubmitting(btn, true);
  const { error } = await signIn(emailEl.value.trim(), passwordEl.value);
  if (error) {
    setSubmitting(btn, false);
    showError('signin-error', error.message || 'Sign-in failed. Check your email and password.');
    return;
  }

  location.href = sessionStorage.getItem('returnTo') || '/';
});

// ---------------------------------------------------------------------------
// Sign-up form
// ---------------------------------------------------------------------------

const signupForm = document.getElementById('form-signup');

signupForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  hideError('signup-error');
  hideError('signup-success');

  const emailEl    = document.getElementById('signup-email');
  const passwordEl = document.getElementById('signup-password');
  const confirmEl  = document.getElementById('signup-confirm');
  const btn        = document.getElementById('signup-btn');

  // Client-side validation
  let valid = true;
  if (!emailEl.value.trim() || !emailEl.validity.valid) {
    setFieldError(emailEl, 'signup-email-error', true);
    valid = false;
  } else {
    setFieldError(emailEl, 'signup-email-error', false);
  }
  if (passwordEl.value.length < 6) {
    setFieldError(passwordEl, 'signup-password-error', true);
    valid = false;
  } else {
    setFieldError(passwordEl, 'signup-password-error', false);
  }
  if (confirmEl.value !== passwordEl.value) {
    setFieldError(confirmEl, 'signup-confirm-error', true);
    valid = false;
  } else {
    setFieldError(confirmEl, 'signup-confirm-error', false);
  }
  if (!valid) return;

  setSubmitting(btn, true);
  const { error } = await signUp(emailEl.value.trim(), passwordEl.value);
  setSubmitting(btn, false);

  if (error) {
    showError('signup-error', error.message || 'Account creation failed. Please try again.');
    return;
  }

  // Success — show confirmation message and hide the form fields so the
  // user reads the instruction rather than trying to submit again.
  signupForm.querySelectorAll('.form-group').forEach(g => (g.style.display = 'none'));
  btn.style.display = 'none';
  document.getElementById('signup-success').classList.add('visible');
});
