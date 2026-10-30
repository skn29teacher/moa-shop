const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const context = { URLSearchParams };
vm.createContext(context);
vm.runInContext(fs.readFileSync(path.join(__dirname, '../static/js/auth-confirmation.js'), 'utf8'), context);

function consume(url) {
  const replacements = [];
  const result = context.consumeAuthConfirmation(new URL(url), {
    replaceState: (_state, _title, target) => replacements.push(target),
  });
  return { result, replacements };
}

test('email success clears tokens and opens login on the deployed origin', () => {
  assert.deepEqual(consume('https://kyuyounglee.pythonanywhere.com/auth/confirm#access_token=FAKE&refresh_token=FAKE&type=signup'), {
    result: 'confirmed', replacements: ['/#/login'],
  });
});
test('legacy root callback and reordered parameters also open login', () => {
  assert.deepEqual(consume('http://127.0.0.1:8000/#expires_in=3600&access_token=FAKE'), {
    result: 'confirmed', replacements: ['/#/login'],
  });
});
test('expired or failed verification is not reported as success', () => {
  assert.deepEqual(consume('https://shop.test/auth/confirm#error=access_denied&error_code=otp_expired'), {
    result: 'error', replacements: ['/#/login'],
  });
});
test('a callback without verification result only invites login', () => {
  assert.deepEqual(consume('https://shop.test/auth/confirm?next=https://untrusted.test'), {
    result: 'pending', replacements: ['/#/login'],
  });
});
test('regular application routes remain accessible', () => {
  assert.deepEqual(consume('https://shop.test/#/products'), { result: null, replacements: [] });
});
