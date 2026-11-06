/* markdown-it with raw HTML and remote images disabled for untrusted AI output. */
const chatMarkdown = (() => {
  const parser = window.markdownit({ html: false, breaks: true, linkify: false });
  parser.disable("image");
  parser.renderer.rules.table_open = () => '<div class="chat-table-scroll" role="region" aria-label="AI 답변 표" tabindex="0"><table>\n';
  parser.renderer.rules.table_close = () => '</table></div>\n';
  const linkOpen = parser.renderer.rules.link_open;
  parser.renderer.rules.link_open = (tokens, index, options, env, renderer) => {
    tokens[index].attrSet("target", "_blank");
    tokens[index].attrSet("rel", "noopener noreferrer");
    return linkOpen ? linkOpen(tokens, index, options, env, renderer) : renderer.renderToken(tokens, index, options);
  };
  return { render: text => parser.render(String(text ?? "")) };
})();
