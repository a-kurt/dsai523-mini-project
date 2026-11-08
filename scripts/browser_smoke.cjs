/* Real browser + real Flask/SQL database. Only TMDB HTTP responses are fixtures. */
const { chromium } = require('playwright');
const { spawn } = require('node:child_process');
const { mkdtempSync, mkdirSync, rmSync } = require('node:fs');
const { tmpdir } = require('node:os');
const path = require('node:path');
const assert = require('node:assert/strict');
const { randomUUID } = require('node:crypto');
const fixtureId = randomUUID();
const root = path.resolve(__dirname, '..');
const work = mkdtempSync(path.join(tmpdir(), 'movie-court-browser-'));
const port = Number(process.env.BROWSER_TEST_PORT || 5088);
const base = `http://127.0.0.1:${port}`;
const artifacts = process.env.BROWSER_ARTIFACTS || '/tmp/movie-court-browser-artifacts';
mkdirSync(artifacts, { recursive: true });
const fixture = `
import sys
from movie_court import create_app
from movie_court.models import db
from movie_court import tmdb
movie={'id':809,'title':'Shrek 2','release_date':'2004-05-19','overview':'An ogre visits his in-laws.','poster_path':None}
class Response:
 def __init__(self,data): self.data=data
 def raise_for_status(self): pass
 def json(self): return self.data
def upstream(url,**kwargs):
 assert kwargs['headers']['Authorization']=='Bearer browser-test-fixture'
 return Response({'results':[movie]} if url.endswith('search/movie') else movie)
tmdb.requests.get=upstream
app=create_app({'TESTING':True,'SECRET_KEY':'browser-test-only-key','SQLALCHEMY_DATABASE_URI':'sqlite:///'+sys.argv[1], 'SESSION_COOKIE_SECURE':False,'RATE_LIMIT_ENABLED':False,'TMDB_READ_TOKEN':'browser-test-fixture'})
app.add_url_rule('/__browser_fixture/'+sys.argv[3], view_func=lambda: sys.argv[3])
with app.app_context(): db.create_all()
app.run(host='127.0.0.1',port=int(sys.argv[2]),use_reloader=False)
`;
const child = spawn(process.env.PYTHON || 'python', ['-c', fixture, path.join(work, 'browser.sqlite'), String(port), fixtureId], { cwd: root, env: { ...process.env, APP_ENV: 'development', TRUST_PROXY: '0', PYTHONPATH: root }, stdio: ['ignore', 'ignore', 'pipe'] });
let serverErrors = '';
child.stderr.on('data', (d) => { serverErrors += d.toString(); });
let browser;
const errors = [];
async function ready() {
  for (let attempt = 0; attempt < 100; attempt++) {
    if (child.exitCode !== null) throw new Error(`Test server stopped: ${serverErrors}`);
    try { const response = await fetch(base + '/__browser_fixture/' + fixtureId); if (response.ok && await response.text() === fixtureId) return; } catch {}
    await new Promise((r) => setTimeout(r, 100));
  }
  throw new Error(`Test server did not start: ${serverErrors}`);
}
async function register(name) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const page = await context.newPage();
  page.on('pageerror', (error) => errors.push(error.message));
  page.on('dialog', (dialog) => dialog.accept());
  await page.goto(base);
  await page.locator('#auth-button').click();
  await page.locator('#register-tab').click();
  await page.locator('#username').fill(name);
  await page.locator('#password').fill('browser testing password');
  await page.locator('#auth-submit').click();
  await page.locator('#account-name').filter({ hasText: name }).waitFor();
  return page;
}
async function reopen(page) {
  await page.reload();
  await page.locator('.case-card').first().click();
  await page.locator('#courtroom-title').waitFor();
}
(async () => {
  await ready();
  browser = await chromium.launch({ executablePath: process.env.BROWSER_BIN || '/usr/bin/chromium', headless: true, args: ['--no-sandbox'] });
  const landing = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  await landing.goto(base);
  await landing.getByText('Every great argument starts here.').waitFor();
  await landing.screenshot({ path: path.join(artifacts, 'landing.png'), fullPage: true });
  const mobile = await browser.newPage({ viewport: { width: 390, height: 844 } });
  await mobile.goto(base);
  await mobile.getByText('Every great argument starts here.').waitFor();
  assert(await mobile.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), 'Mobile page has horizontal overflow');
  await mobile.screenshot({ path: path.join(artifacts, 'mobile.png'), fullPage: true });
  const judge = await register('browser_judge');
  await judge.locator('#open-case-button').click();
  await judge.locator('#movie-query').fill('Shrek');
  await judge.locator('#movie-search-form').getByRole('button', { name: 'Search', exact: true }).click();
  await judge.locator('.movie-result').first().click();
  await judge.locator('#case-charge').fill('Shrek 2 is the greatest sequel ever.');
  await judge.locator('#create-form').getByRole('button').click();
  await judge.locator('#courtroom-title').waitFor();
  assert.match(await judge.locator('#courtroom-title').innerText(), /Shrek 2/);
  const guests = {};
  for (const role of ['prosecutor', 'defender', 'juror']) {
    await judge.locator('#invite-role').selectOption(role);
    await judge.getByRole('button', { name: 'Create invite token' }).click();
    await judge.locator('.token-box code').waitFor();
    const token = await judge.locator('.token-box code').innerText();
    assert(token.length >= 40);
    const guest = await register(`browser_${role}`);
    await guest.locator('#join-button').click();
    await guest.locator('#invite-token').fill(token);
    await guest.locator('#join-form').getByRole('button', { name: 'Accept invitation' }).click();
    await guest.locator('#courtroom-title').waitFor();
    assert.match(await guest.locator('.role-chip').innerText(), new RegExp(role, 'i'));
    guests[role] = guest;
  }
  const argument = 'Exhibit A: the soundtrack. <img src=x onerror="window.bad=true">';
  await guests.prosecutor.locator('#argument-body').fill(argument);
  await guests.prosecutor.getByRole('button', { name: 'Submit to the record' }).click();
  await guests.prosecutor.locator('.argument-body').filter({ hasText: argument }).waitFor();
  assert.equal(await guests.prosecutor.evaluate(() => window.bad), undefined, 'Argument rendered as HTML');
  await guests.prosecutor.locator('.argument-tools').getByRole('button', { name: 'Edit', exact: true }).click();
  await guests.prosecutor.locator('#edit-argument-body').fill('Exhibit A: the soundtrack is unbeatable.');
  await guests.prosecutor.locator('#edit-form').getByRole('button', { name: 'Save changes' }).click();
  await guests.prosecutor.getByText('Exhibit A: the soundtrack is unbeatable.', { exact: true }).waitFor();
  await guests.defender.locator('#argument-body').fill('The first film deserves some credit.');
  await guests.defender.getByRole('button', { name: 'Submit to the record' }).click();
  await guests.defender.getByText('The first film deserves some credit.', { exact: true }).waitFor();
  await reopen(judge);
  await judge.getByRole('button', { name: 'Edit case', exact: true }).click();
  await judge.locator('#edit-case-title').fill('The People vs. Shrek 2');
  await judge.locator('#edit-form').getByRole('button', { name: 'Save changes' }).click();
  await judge.locator('#edit-dialog').waitFor({ state: 'hidden' });
  await judge.getByRole('button', { name: 'Open jury voting' }).click();
  await judge.getByRole('heading', { name: 'The jury is deliberating.' }).waitFor();
  assert.equal(await judge.getByRole('button', { name: 'Guilty', exact: true }).count(), 0, 'Judge can see a vote button');
  await reopen(guests.juror);
  await guests.juror.getByRole('button', { name: 'Guilty', exact: true }).click();
  await guests.juror.getByText('Your vote is sealed: Guilty.', { exact: true }).waitFor();
  assert.equal(await guests.juror.locator('.verdict-counts').count(), 0, 'Early totals leak');
  await judge.getByRole('button', { name: 'Close voting & reveal verdict' }).click();
  await judge.getByRole('heading', { name: 'Guilty.', exact: true }).waitFor();
  await judge.getByText('1 vote on the record. Case closed.', { exact: true }).waitFor();
  await judge.screenshot({ path: path.join(artifacts, 'verdict.png'), fullPage: true });
  await judge.locator('#logout-button').click();
  await judge.locator('#auth-button').waitFor();
  assert.equal(await judge.locator('.token-box code').count(), 0);
  assert.deepEqual(errors, [], 'Browser JavaScript errors');
  console.log('PASS: registration, search, case creation/edit, role invites, arguments/edit, XSS escaping, vote privacy, verdict, logout, mobile layout.');
  console.log('TMDB responses were test fixtures. Artifacts: ' + artifacts);
})().catch((error) => { console.error(error); process.exitCode = 1; }).finally(async () => {
  if (browser) await browser.close();
  child.kill('SIGTERM');
  rmSync(work, { recursive: true, force: true });
});
