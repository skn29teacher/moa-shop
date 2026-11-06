const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const markdownit = require('../static/vendor/markdown-it/markdown-it.min.js');
const context = vm.createContext({ window: { markdownit } });
vm.runInContext(fs.readFileSync(path.join(__dirname, '../static/js/chat-markdown.js'), 'utf8'), context);
const render = text => vm.runInContext('chatMarkdown.render(input)', Object.assign(context, { input: text }));

test('gift recommendation becomes an accessible HTML table with formatted prices', () => {
  const html = render('선물을 추천해요.\n\n| 조합 | 상품 | 가격 | 재고 |\n|------|------|------|------|\n| 1 | 티셔츠 + 텀블러 | **44,000원** | 28, 5 |\n| 2 | 에코백 + 티셔츠 + 텀블러 | 59,000원 | 15, 28, 5 |\n\n※ 재고를 확인해 주세요.');
  assert.match(html, /role="region" aria-label="AI 답변 표" tabindex="0"/);
  assert.match(html, /<table>/);
  assert.match(html, /<th>조합<\/th>/);
  assert.match(html, /<strong>44,000원<\/strong>/);
  assert.equal((html.match(/<tr>/g) || []).length, 3);
  assert.match(html, /<p>※ 재고를 확인해 주세요\.<\/p>/);
});

test('headings, lists, paragraphs and fenced code render', () => {
  const html = render('## 추천\n\n- **가방**\n- *티셔츠*\n\n1. 상품 확인\n2. 주문\n\n첫 줄\n둘째 줄\n\n```html\n<script>alert(1)</script>\n```');
  for (const tag of ['h2', 'ul', 'ol', 'strong', 'em', 'pre', 'code']) assert.match(html, new RegExp(`<${tag}[ >]`));
  assert.match(html, /첫 줄<br>\n둘째 줄/);
  assert.ok(!html.includes('<script>'));
});

test('raw HTML, SVG and event handlers remain escaped text', () => {
  const html = render('<script>alert(1)</script>\n<img src=x onerror=alert(1)>\n<svg onload=alert(1)>\n<iframe src="https://example.com"></iframe>');
  assert.ok(!/<(?:script|img|svg|iframe)\b/i.test(html));
  assert.match(html, /&lt;script&gt;/);
});

test('unsafe Markdown URLs cannot create executable links', () => {
  for (const url of ['javascript:alert(1)', 'jav&#x61;script:alert(1)', 'vbscript:msgbox(1)', 'data:text/html,hello', 'file:///etc/passwd']) {
    const html = render(`[클릭](${url})`);
    assert.ok(!html.includes('<a '), html);
  }
});

test('safe links use a separate tab without opener access and remote images do not load', () => {
  const html = render('[상품](https://example.com/product?q=1&x=2)\n\n![추적 이미지](https://example.com/tracker.png)');
  assert.match(html, /target="_blank"/);
  assert.match(html, /rel="noopener noreferrer"/);
  assert.ok(!html.includes('<img'));
});

test('HTML inside table cells is also escaped', () => {
  const html = render('| 상품 |\n| --- |\n| <img src=x onerror=alert(1)> |');
  assert.match(html, /<table>/);
  assert.match(html, /&lt;img/);
  assert.ok(!html.includes('<img'));
});
