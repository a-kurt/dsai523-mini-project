/* Movie Court uses one same-origin API. Private data stays in memory, never in local storage. */
'use strict';

const $ = (id) => document.getElementById(id);
const state = { user: null, csrf: '', mode: 'login', movie: null, current: null, edit: null, noticeTimer: null, loadingCase: 0 };
const phaseNames = { debate: 'Arguments open', voting: 'Jury deliberation', closed: 'Verdict delivered' };
const roleNames = { judge: 'Judge', prosecutor: 'Prosecutor', defender: 'Defender', juror: 'Juror' };
const verdictNames = { guilty: 'Guilty.', not_guilty: 'Not guilty.', tie: 'A divided jury.', no_votes: 'No verdict.' };

function node(tag, className, text) {
  const el = document.createElement(tag);
  if (className) el.className = className;
  if (text !== undefined && text !== null) el.textContent = String(text);
  return el;
}
function button(text, className, action) {
  const el = node('button', className, text);
  el.type = 'button';
  el.addEventListener('click', action);
  return el;
}
function notify(message, error = false) {
  clearTimeout(state.noticeTimer);
  $('notice').textContent = message;
  $('notice').classList.toggle('error', error);
  $('notice').hidden = false;
  state.noticeTimer = setTimeout(() => { $('notice').hidden = true; }, error ? 9000 : 5000);
}
function formError(id, message = '') {
  $(id).textContent = message;
  $(id).hidden = !message;
}
async function api(path, method = 'GET', data) {
  const headers = { Accept: 'application/json' };
  if (method !== 'GET') headers['X-CSRF-Token'] = state.csrf;
  if (data !== undefined) headers['Content-Type'] = 'application/json';
  let response;
  try {
    response = await fetch(path, { method, headers, credentials: 'same-origin', body: data === undefined ? undefined : JSON.stringify(data), cache: 'no-store' });
  } catch (_) { throw new Error('The court could not be reached. Check your connection and try again.'); }
  const content = response.status === 204 ? {} : await response.json().catch(() => ({}));
  if (!response.ok) {
    // Refresh identity after an expired session without replaying a write request.
    if ([401, 403].includes(response.status) && path !== '/api/auth/me') {
      try { await refreshIdentity(); } catch (_) { /* Keep the original request error. */ }
    }
    throw new Error(content.error || `The request could not be completed (${response.status}). Please try again.`);
  }
  return content;
}
async function busy(el, task, errorId) {
  const wasDisabled = el?.disabled;
  if (el) { el.disabled = true; el.setAttribute('aria-busy', 'true'); }
  if (errorId) formError(errorId);
  try { return await task(); }
  catch (error) {
    if (errorId) {
      formError(errorId, error.message);
      if (!$(errorId).closest('dialog')?.open) notify(error.message, true);
    } else notify(error.message, true);
  }
  finally { if (el) { el.disabled = Boolean(wasDisabled); el.removeAttribute('aria-busy'); } }
}
function showDialog(id) {
  for (const dialog of document.querySelectorAll('dialog[open]')) dialog.close();
  $(id).showModal();
}
function requireUser(action) {
  if (state.user) action();
  else { openAuth(); notify('Sign in first, then choose your next move.'); }
}
async function refreshIdentity() {
  const data = await api('/api/auth/me');
  const lostSession = state.user && !data.user;
  state.user = data.user;
  state.csrf = data.csrf_token;
  if (lostSession) {
    state.loadingCase += 1;
    state.current = null;
    state.movie = null;
    state.edit = null;
    for (const dialog of document.querySelectorAll('dialog[open]')) dialog.close();
    $('courtroom').hidden = true;
    $('courtroom').replaceChildren();
    $('docket').hidden = false;
    $('hero').hidden = false;
    document.querySelector('.how-strip').hidden = false;
    renderSignedOut();
  }
  updateAccount();
}
function updateAccount() {
  $('auth-button').hidden = Boolean(state.user);
  $('logout-button').hidden = !state.user;
  $('account-name').hidden = !state.user;
  $('account-name').textContent = state.user ? state.user.username : '';
  $('refresh-button').hidden = !state.user;
}
function setAuthMode(mode) {
  state.mode = mode;
  const login = mode === 'login';
  $('login-tab').classList.toggle('active', login);
  $('register-tab').classList.toggle('active', !login);
  $('login-tab').setAttribute('aria-pressed', String(login));
  $('register-tab').setAttribute('aria-pressed', String(!login));
  $('auth-title').textContent = login ? 'Take your seat.' : 'Join the court.';
  $('auth-description').textContent = login ? 'Sign in to open your private case files.' : 'Pick a name. Bring your strongest movie opinions.';
  $('password').autocomplete = login ? 'current-password' : 'new-password';
  $('auth-submit').textContent = login ? 'Sign in →' : 'Create account →';
  formError('auth-error');
}
function openAuth() { setAuthMode('login'); $('auth-form').reset(); showDialog('auth-dialog'); }
function emptyState(icon, title, description, actionText, action, error = false) {
  const box = node('div', `empty-state${error ? ' error-state' : ''}`);
  box.append(node('div', 'empty-icon', icon), node('h3', '', title), node('p', '', description));
  if (action) box.append(button(actionText, 'button button-outline', action));
  return box;
}
function renderSignedOut() {
  $('docket-content').replaceChildren(emptyState('⚖', 'Every great argument starts here.', 'Your case files are private. Sign in to put a movie on trial or accept an invitation from a friend.', 'Take your seat →', openAuth));
}
async function loadDocket() {
  if (!state.user) { renderSignedOut(); return; }
  const requestedUserId = state.user.id;
  $('docket-content').replaceChildren(node('p', 'loading-message', 'Retrieving your case files…'));
  try {
    const data = await api('/api/cases');
    if (state.user?.id !== requestedUserId) return;
    if (!data.cases.length) {
      const empty = emptyState('▤', 'A clean record. For now.', 'No cases on your docket yet. File your first case, or join a friend’s court with an invite token.', 'File a new case →', openCreate);
      empty.append(node('br'), button('Accept an invitation →', 'text-button', () => showDialog('join-dialog')));
      $('docket-content').replaceChildren(empty);
      return;
    }
    const grid = node('div', 'case-grid');
    data.cases.forEach((courtCase) => {
      const card = button('', 'case-card', () => busy(card, () => openCase(courtCase.id)));
      const meta = node('div', 'case-meta');
      meta.append(node('span', '', `CASE ${String(courtCase.id).padStart(3, '0')}`), phaseBadge(courtCase.phase));
      const bottom = node('div', 'case-card-bottom');
      bottom.append(node('span', '', 'Enter the courtroom'), node('span', '', '→'));
      card.append(meta, node('h3', '', courtCase.title), node('p', '', `${courtCase.movie.title}${year(courtCase.movie.release_date)}`), bottom);
      grid.append(card);
    });
    $('docket-content').replaceChildren(grid);
  } catch (error) {
    if (!state.user) { renderSignedOut(); return; }
    $('docket-content').replaceChildren(emptyState('!', 'The files are taking a recess.', error.message, 'Try again ↻', loadDocket, true));
  }
}
function year(date) { return date ? ` (${String(date).slice(0, 4)})` : ''; }
function phaseBadge(phase) { return node('span', `phase phase-${phase}`, phaseNames[phase] || phase); }
function openCreate() {
  $('create-form').reset();
  $('movie-search-form').reset();
  $('create-form').hidden = true;
  $('movie-results').replaceChildren();
  formError('create-error');
  state.movie = null;
  showDialog('create-dialog');
}
function chooseMovie(movie, resultButton) {
  state.movie = movie;
  document.querySelectorAll('.movie-result').forEach((el) => el.setAttribute('aria-pressed', String(el === resultButton)));
  $('selected-movie').textContent = `The accused: ${movie.title}${year(movie.release_date)}`;
  $('case-title').value = `The People vs. ${movie.title}`.slice(0, 120);
  $('create-form').hidden = false;
  $('case-charge').focus();
}
async function openCase(id) {
  const request = ++state.loadingCase;
  const data = await api(`/api/cases/${id}`);
  if (request !== state.loadingCase) return;
  state.current = data;
  $('hero').hidden = true;
  $('docket').hidden = true;
  document.querySelector('.how-strip').hidden = true;
  $('courtroom').hidden = false;
  renderCourt(data);
  $('courtroom').scrollIntoView({ behavior: 'smooth', block: 'start' });
  const heading = $('courtroom-title');
  heading.tabIndex = -1;
  heading.focus({ preventScroll: true });
}
function goDocket() {
  state.loadingCase += 1;
  state.current = null;
  $('courtroom').hidden = true;
  $('courtroom').replaceChildren();
  $('hero').hidden = false;
  $('docket').hidden = false;
  document.querySelector('.how-strip').hidden = false;
  loadDocket();
  $('docket').scrollIntoView({ behavior: 'smooth' });
}
function panel(title, className = '') {
  const el = node('section', `court-panel ${className}`);
  if (title) el.append(node('h3', '', title));
  return el;
}
function renderCourt(data) {
  const c = data.case;
  const court = $('courtroom');
  const nav = node('div', 'court-nav');
  const back = button('← Back to your docket', 'text-button back-button', goDocket);
  const refresh = button('Refresh court ↻', 'text-button back-button', () => busy(refresh, () => openCase(c.id)));
  nav.append(back, refresh);
  const top = node('div', 'court-top');
  const headingWrap = node('div');
  const eyebrow = node('p', 'eyebrow', `CASE ${String(c.id).padStart(3, '0')} / THE COURT OF CINEMATIC OPINION`);
  const title = node('h2', '', c.title); title.id = 'courtroom-title';
  headingWrap.append(eyebrow, phaseBadge(c.phase), title, node('p', 'movie-name', `${c.movie.title}${year(c.movie.release_date)}`));
  top.append(headingWrap, node('span', 'role-chip', `Your role: ${roleNames[data.my_role] || data.my_role}`));
  const layout = node('div', 'court-layout');
  const main = node('div', 'court-main');
  const side = node('aside', 'court-sidebar');
  const charge = panel('', 'charge-panel');
  charge.append(node('p', 'eyebrow', 'THE CHARGE'), node('p', 'charge-text', c.charge), node('p', 'field-help', 'Guilty = the charge is true. Not guilty = the charge is false.'));
  if (data.my_role === 'judge') appendJudgeActions(charge, data);
  main.append(charge);
  if (data.verdict) main.append(verdictPanel(data.verdict));
  else if (c.phase === 'voting') main.append(ballotPanel(data));
  const argumentsPanel = panel('Arguments on the record');
  if (!data.arguments.length) argumentsPanel.append(node('p', 'muted', 'The record is empty. The prosecutor and defender can make their opening arguments during the debate.'));
  data.arguments.forEach((argument) => argumentsPanel.append(argumentItem(argument, data)));
  if (c.phase === 'debate' && ['prosecutor', 'defender'].includes(data.my_role)) argumentsPanel.append(argumentForm(c.id));
  else argumentsPanel.append(node('p', 'phase-hint', c.phase === 'debate' ? 'The prosecutor and defender present arguments. Jurors listen and vote when the judge opens voting.' : 'The arguments are now part of the court record and cannot be changed.'));
  main.append(argumentsPanel);
  const members = panel('The court');
  const list = node('ul', 'member-list');
  data.members.forEach((member) => {
    const li = node('li');
    const name = node('div', 'member-name', member.username + (member.user_id === state.user.id ? ' (you)' : ''));
    name.append(node('span', 'member-role', roleNames[member.role] || member.role));
    li.append(node('span', 'member-avatar', member.username.slice(0, 1).toUpperCase()), name);
    list.append(li);
  });
  members.append(list); side.append(members);
  if (data.my_role === 'judge' && c.phase === 'debate') side.append(invitePanel(c.id));
  const moviePanel = panel('Exhibit A');
  moviePanel.append(node('p', 'eyebrow', 'MOVIE DETAILS'), node('strong', '', c.movie.title), node('p', 'movie-overview', c.movie.overview || 'No overview is available for this film.'));
  side.append(moviePanel);
  layout.append(main, side);
  court.replaceChildren(nav, top, layout);
}
function appendJudgeActions(container, data) {
  const c = data.case;
  const actions = node('div', 'court-actions');
  if (c.phase === 'debate') {
    actions.append(button('Edit case', 'button button-outline', () => editCase(c)));
    const open = button('Open jury voting →', 'button button-gold', () => {
      if (!confirm('Close the arguments and open jury voting? Arguments and invitations will be locked.')) return;
      busy(open, async () => { await api(`/api/cases/${c.id}/phase`, 'POST', { phase: 'voting' }); await openCase(c.id); notify('The jury may now vote.'); });
    });
    actions.append(open);
    container.append(node('p', 'phase-hint', 'Before voting, invite one prosecutor, one defender, and at least one juror. Each person needs their own account.'));
  } else if (c.phase === 'voting') {
    const close = button('Close voting & reveal verdict →', 'button button-gold', () => {
      if (!confirm('Reveal the verdict now? Jurors who have not voted will lose their chance. This cannot be undone.')) return;
      busy(close, async () => { await api(`/api/cases/${c.id}/phase`, 'POST', { phase: 'closed' }); await openCase(c.id); notify('The verdict is in.'); });
    }); actions.append(close);
    container.append(node('p', 'phase-hint', 'Votes stay private until you close the case. Wait for your jury before revealing the verdict.'));
  }
  container.append(actions);
  const danger = node('div', 'danger-zone');
  const remove = button('Delete this case', 'text-button', () => {
    if (!confirm('Delete this case, its arguments, invites, and votes? This cannot be undone.')) return;
    busy(remove, async () => { await api(`/api/cases/${c.id}`, 'DELETE'); goDocket(); notify('The case has been deleted.'); });
  }); danger.append(remove); container.append(danger);
}
function invitePanel(id) {
  const box = panel('Call the court', 'invite-panel');
  box.append(node('p', 'muted', 'Create a private, single-use token. Share it directly with one friend.'));
  const form = node('form');
  const label = node('label', '', 'Invite as'); label.htmlFor = 'invite-role';
  const role = node('select'); role.id = 'invite-role'; role.name = 'role';
  ['juror', 'prosecutor', 'defender'].forEach((r) => { const option = node('option', '', roleNames[r]); option.value = r; role.append(option); });
  const submit = node('button', 'button button-outline full-width', 'Create invite token →'); submit.type = 'submit';
  const result = node('div');
  form.append(label, role, submit);
  form.addEventListener('submit', (e) => {
    e.preventDefault();
    busy(submit, async () => {
      result.replaceChildren();
      const data = await api(`/api/cases/${id}/invites`, 'POST', { role: role.value });
      const tokenBox = node('div', 'token-box');
      tokenBox.append(node('code', '', data.token), node('p', '', `Copy this now. It is shown only here. Expires ${formatDate(data.expires_at)}.`));
      const copy = button('Copy token', 'button button-small button-outline', () => busy(copy, async () => {
        if (!navigator.clipboard?.writeText) { notify('Select the token text and copy it manually.'); return; }
        try { await navigator.clipboard.writeText(data.token); notify('Token copied. Share it privately.'); }
        catch (_) { notify('Select the token text and copy it manually.'); }
      }));
      tokenBox.append(copy); result.append(tokenBox);
    });
  });
  const revoke = button('Revoke all unused invites', 'text-button', () => {
    if (!confirm('Cancel all unused invitations for this case? Existing court members will keep their roles.')) return;
    busy(revoke, async () => { await api(`/api/cases/${id}/invites`, 'DELETE'); result.replaceChildren(); notify('Unused invites have been revoked.'); });
  });
  box.append(form, result, revoke);
  return box;
}
function formatDate(value) { const date = new Date(value); return Number.isNaN(date.getTime()) ? 'soon' : date.toLocaleString(); }
function argumentItem(argument, data) {
  const article = node('article', 'argument');
  const header = node('div', 'argument-heading');
  header.append(node('strong', '', argument.username), node('span', '', roleNames[argument.role] || argument.role));
  article.append(header, node('p', 'argument-body', argument.body), node('p', 'argument-time', formatDate(argument.created_at)));
  if (argument.user_id === state.user.id && data.case.phase === 'debate') {
    const tools = node('div', 'argument-tools');
    const edit = button('Edit', 'text-button', () => editArgument(argument, data.case.id));
    const remove = button('Delete', 'text-button', () => {
      if (!confirm('Delete this argument from the record?')) return;
      busy(remove, async () => { await api(`/api/cases/${data.case.id}/arguments/${argument.id}`, 'DELETE'); await openCase(data.case.id); notify('Argument deleted.'); });
    });
    tools.append(edit, remove); article.append(tools);
  }
  return article;
}
function argumentForm(id) {
  const form = node('form');
  const label = node('label', '', 'Your argument'); label.htmlFor = 'argument-body';
  const body = node('textarea'); body.id = 'argument-body'; body.rows = 4; body.maxLength = 4000; body.required = true; body.placeholder = 'Make your case. Cite a scene. Defend the indefensible.';
  const submit = node('button', 'button button-gold full-width', 'Submit to the record →'); submit.type = 'submit';
  form.append(label, body, node('p', 'field-help', 'Keep it about the movie. You can edit your argument until voting starts.'), submit);
  form.addEventListener('submit', (e) => { e.preventDefault(); busy(submit, async () => { await api(`/api/cases/${id}/arguments`, 'POST', { body: body.value }); await openCase(id); notify('Your argument is on the record.'); }); });
  return form;
}
function ballotPanel(data) {
  const box = panel('The jury is deliberating.', 'ballot-panel');
  if (data.my_role !== 'juror') { box.append(node('p', '', 'Only assigned jurors can vote. The result stays sealed until the judge closes the case.')); return box; }
  if (data.my_vote) { box.append(node('p', 'ballot-saved', `Your vote is sealed: ${data.my_vote === 'guilty' ? 'Guilty' : 'Not guilty'}.`), node('p', '', 'You have one vote. It cannot be changed. The full result appears when the judge closes the case.')); return box; }
  box.append(node('p', '', 'Read the charge and arguments, then cast your private vote. You can vote only once, and cannot change it.'));
  const options = node('div', 'ballot-options');
  ['guilty', 'not_guilty'].forEach((choice) => {
    const text = choice === 'guilty' ? 'Guilty' : 'Not guilty';
    const vote = button(text, choice === 'guilty' ? 'button button-gold' : 'button button-outline', () => {
      if (!confirm(`Seal your vote as “${text}”? You cannot change it.`)) return;
      busy(vote, async () => { await api(`/api/cases/${data.case.id}/votes`, 'POST', { choice }); await openCase(data.case.id); notify('Your vote has been sealed.'); });
    }); options.append(vote);
  }); box.append(options); return box;
}
function verdictPanel(verdict) {
  const box = panel('', 'verdict-panel');
  box.append(node('p', 'eyebrow', 'THE JURY HAS SPOKEN'), node('h3', '', verdictNames[verdict.result] || 'The verdict is in.'));
  const counts = node('div', 'verdict-counts');
  [['Guilty', verdict.guilty], ['Not guilty', verdict.not_guilty]].forEach(([label, count]) => { const col = node('div'); col.append(node('strong', '', count), node('span', '', label)); counts.append(col); });
  box.append(counts, node('p', 'phase-hint', `${verdict.total} vote${verdict.total === 1 ? '' : 's'} on the record. Case closed.`));
  return box;
}
function editField(id, labelText, value, max, multiline = false) {
  const wrap = node('div');
  const label = node('label', '', labelText); label.htmlFor = id;
  const input = node(multiline ? 'textarea' : 'input'); input.id = id; input.value = value; input.maxLength = max; input.required = true;
  if (multiline) input.rows = 5;
  wrap.append(label, input); return wrap;
}
function editCase(c) {
  state.edit = { kind: 'case', caseId: c.id };
  $('edit-title').textContent = 'Edit the case.';
  $('edit-fields').replaceChildren(editField('edit-case-title', 'Case title', c.title, 120), editField('edit-case-charge', 'The charge', c.charge, 1000, true));
  formError('edit-error'); showDialog('edit-dialog');
}
function editArgument(argument, caseId) {
  state.edit = { kind: 'argument', caseId, argumentId: argument.id };
  $('edit-title').textContent = 'Edit your argument.';
  $('edit-fields').replaceChildren(editField('edit-argument-body', 'Your argument', argument.body, 4000, true));
  formError('edit-error'); showDialog('edit-dialog');
}

// Bind static controls once. Dynamic courtroom controls are recreated after each successful change.
$('auth-button').addEventListener('click', openAuth);
$('login-tab').addEventListener('click', () => setAuthMode('login'));
$('register-tab').addEventListener('click', () => setAuthMode('register'));
$('open-case-button').addEventListener('click', () => requireUser(openCreate));
$('join-button').addEventListener('click', () => requireUser(() => { $('join-form').reset(); formError('join-error'); showDialog('join-dialog'); }));
$('refresh-button').addEventListener('click', () => busy($('refresh-button'), loadDocket));
document.querySelectorAll('[data-close]').forEach((el) => el.addEventListener('click', () => el.closest('dialog').close()));
document.querySelectorAll('dialog').forEach((dialog) => dialog.addEventListener('close', () => {
  if (dialog.id === 'join-dialog') $('invite-token').value = '';
  if (dialog.id === 'auth-dialog') $('password').value = '';
}));
$('auth-form').addEventListener('submit', (e) => {
  e.preventDefault();
  busy($('auth-submit'), async () => {
    await api(`/api/auth/${state.mode}`, 'POST', { username: $('username').value.trim(), password: $('password').value });
    await refreshIdentity();
    $('auth-dialog').close();
    $('password').value = '';
    await loadDocket();
    notify(`Welcome to the court, ${state.user.username}.`);
  }, 'auth-error');
});
$('logout-button').addEventListener('click', () => busy($('logout-button'), async () => {
  await api('/api/auth/logout', 'POST');
  for (const dialog of document.querySelectorAll('dialog[open]')) dialog.close();
  state.user = null; state.current = null; state.movie = null; state.edit = null;
  await refreshIdentity();
  goDocket();
  notify('You have signed out.');
}));
$('movie-search-form').addEventListener('submit', (e) => {
  e.preventDefault();
  busy(e.submitter, async () => {
    $('movie-results').replaceChildren(node('p', 'loading-message', 'Finding the accused…'));
    const query = $('movie-query').value.trim();
    try {
      const data = await api(`/api/movies/search?q=${encodeURIComponent(query)}`);
      $('movie-results').replaceChildren();
      if (!data.movies.length) $('movie-results').append(node('p', 'muted', 'No films found. Try another title.'));
      data.movies.forEach((movie) => {
        const item = button('', 'movie-result', () => chooseMovie(movie, item));
        item.setAttribute('aria-pressed', 'false');
        item.append(node('strong', '', `${movie.title}${year(movie.release_date)}`), node('p', '', (movie.overview || 'No overview available.').slice(0, 150)));
        $('movie-results').append(item);
      });
    } catch (error) { $('movie-results').replaceChildren(); throw error; }
  }, 'create-error');
});
$('create-form').addEventListener('submit', (e) => {
  e.preventDefault();
  busy(e.submitter, async () => {
    if (!state.movie) throw new Error('Choose a movie first.');
    const data = await api('/api/cases', 'POST', { movie_id: state.movie.id, title: $('case-title').value.trim(), charge: $('case-charge').value.trim() });
    $('create-dialog').close();
    await openCase(data.case.id);
    notify('Case filed. You are the judge. Invite your court to begin.');
  }, 'create-error');
});
$('join-form').addEventListener('submit', (e) => {
  e.preventDefault();
  busy(e.submitter, async () => {
    const data = await api('/api/invites/redeem', 'POST', { token: $('invite-token').value.trim() });
    $('join-dialog').close();
    $('invite-token').value = '';
    await openCase(data.case_id);
    notify(`You joined the court as ${roleNames[data.role] || data.role}.`);
  }, 'join-error');
});
$('edit-form').addEventListener('submit', (e) => {
  e.preventDefault();
  busy(e.submitter, async () => {
    const edit = state.edit;
    if (edit.kind === 'case') await api(`/api/cases/${edit.caseId}`, 'PATCH', { title: $('edit-case-title').value.trim(), charge: $('edit-case-charge').value.trim() });
    else await api(`/api/cases/${edit.caseId}/arguments/${edit.argumentId}`, 'PATCH', { body: $('edit-argument-body').value });
    $('edit-dialog').close();
    await openCase(edit.caseId);
    notify('The record has been updated.');
  }, 'edit-error');
});

(async function boot() {
  try { await refreshIdentity(); await loadDocket(); }
  catch (error) { $('docket-content').replaceChildren(emptyState('!', 'The court could not open.', error.message, 'Reload the page ↻', () => window.location.reload(), true)); }
}());
