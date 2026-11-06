/* Groq-backed chat. Conversation is held in memory for this screen only. */
function chatIcon(name, className = "") {
  const paths = {
    sparkle: '<path d="m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5L12 3Z"/>',
    plus: '<path d="M12 5v14M5 12h14"/>',
    arrow: '<path d="M12 19V5m-6 6 6-6 6 6"/>',
    chevron: '<path d="m9 5 7 7-7 7"/>',
    bag: '<path d="M5 8h14l1 12H4L5 8Z"/><path d="M9 8V6a3 3 0 0 1 6 0v2"/>',
    gift: '<path d="M4 11h16v9H4zM3 7h18v4H3zM12 7v13"/><path d="M12 7H8.5A2.5 2.5 0 1 1 11 4.5L12 7Zm0 0h3.5A2.5 2.5 0 1 0 13 4.5L12 7Z"/>',
    compare: '<path d="M8 4v16M16 4v16M4 8h8M12 16h8"/><circle cx="8" cy="8" r="2"/><circle cx="16" cy="16" r="2"/>',
    box: '<path d="m12 3 9 5-9 5-9-5 9-5Zm-9 5v10l9 5 9-5V8M12 13v10M7 5.8l10 5.5"/>',
    message: '<path d="M20 11.5a8.5 8.5 0 0 1-8.5 8.5H4l-1 1v-9.5a8.5 8.5 0 0 1 17 0Z"/>',
    panel: '<rect x="3" y="4" width="18" height="16" rx="3"/><path d="M9 4v16"/>',
    more: '<circle cx="5" cy="12" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/>',
    check: '<path d="m5 12 4 4L19 6"/>',
    leaf: '<path d="M20 4C8 2 2 8 6 15s16 1 14-11Z"/><path d="M5 20 16 9"/>',
    close: '<path d="m6 6 12 12M6 18 18 6"/>',
  };
  return `<svg class="chat-icon ${className}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name] || paths.sparkle}</svg>`;
}

function renderChatPreview() {
  const suggestions = [
    ["bag", "취향에 맞는 상품 찾기", "나에게 어울리는 일상의 아이템", "데일리로 쓰기 좋은 가방을 추천해 줘"],
    ["gift", "마음을 담은 선물 고르기", "받는 사람도, 주는 사람도 기쁘게", "친구에게 줄 5만 원대 선물을 찾고 있어"],
    ["compare", "고민되는 상품 비교하기", "차이를 알면 선택이 쉬워지니까", "상품을 비교할 때 어떤 점을 확인하면 좋을까?"],
    ["box", "주문·배송 알아보기", "궁금한 내용을 한곳에서", "주문과 배송은 어디에서 확인할 수 있어?"],
  ];
  root.innerHTML = `<div class="chat-workspace">
    <aside class="chat-sidebar" id="chat-sidebar" aria-label="대화 탐색">
      <div class="chat-sidebar-heading"><a href="#/chat" class="chat-wordmark">moa<span> AI</span><span class="chat-beta">BETA</span></a><button type="button" class="chat-icon-button chat-sidebar-close" aria-label="대화 목록 닫기">${chatIcon("close")}</button></div>
      <button class="chat-new" type="button">${chatIcon("plus")}새로운 대화<span>↗</span></button>
      <div class="chat-history"><p class="chat-section-label">대화 미리보기</p>
        <button class="chat-history-item active" type="button" data-chat-home>${chatIcon("message")}새로운 쇼핑의 시작</button>
        <button class="chat-history-item" type="button" data-chat-example>${chatIcon("message")}친구를 위한 집들이 선물<span class="chat-example-label">예시</span></button>
      </div>
      <div class="chat-sidebar-bottom"><div class="chat-discovery">${chatIcon("leaf")}<strong>취향을 발견하는 작은 대화</strong><p>무엇을 찾을지 몰라도 괜찮아요.<br>모아와 함께 천천히 찾아보세요.</p><a href="#/products">상품 먼저 둘러보기 <span>↗</span></a></div>
      <div class="chat-profile"><span class="chat-avatar">M</span><div><strong>모아샵에 오신 걸 환영해요</strong><span>당신의 일상에 좋은 선택</span></div></div></div>
    </aside>
    <button class="chat-backdrop" type="button" aria-label="대화 목록 닫기" hidden></button>
    <section class="chat-main" aria-label="AI 쇼핑 도우미">
      <header class="chat-topbar"><div class="chat-topbar-title"><button class="chat-icon-button chat-sidebar-toggle" type="button" aria-label="대화 목록 열기" aria-expanded="false" aria-controls="chat-sidebar">${chatIcon("panel")}</button><strong>AI 쇼핑 도우미</strong><span class="chat-topbar-divider"></span><span class="chat-topbar-subtitle">당신의 취향을 함께 찾아요</span></div><span class="chat-preview-badge" id="chat-connection"><i></i>연결 확인 중</span></header>
      <div class="chat-stage">
        <div class="chat-welcome" id="chat-welcome"><div class="chat-hero-mark">${chatIcon("sparkle")}</div><p class="chat-kicker">A LITTLE HELP, A BETTER CHOICE</p><h1>어떤 좋은 것을<br><span>찾고 계신가요?</span></h1><p class="chat-intro">막연한 취향부터 꼼꼼한 비교까지.<br>모아와 이야기하며 나에게 맞는 선택을 찾아보세요.</p>
        <div class="chat-suggestions">${suggestions.map(([icon, title, desc, prompt]) => `<button type="button" class="chat-suggestion" data-prompt="${escapeHtml(prompt)}"><span class="chat-suggestion-icon">${chatIcon(icon)}</span><span><strong>${title}</strong><small>${desc}</small></span>${chatIcon("chevron", "chat-card-arrow")}</button>`).join("")}</div>
        <button type="button" class="chat-example-link" data-chat-example>처음이신가요? <span>대화 예시 살펴보기 ${chatIcon("chevron")}</span></button></div>
        <div class="chat-example" id="chat-example" hidden><div class="chat-example-heading"><span>대화 예시</span><button class="chat-text-button" type="button" data-chat-home>시작 화면으로 돌아가기 ↗</button></div><h1>마음을 담은 집들이 선물</h1><div class="chat-user-message">친구 집들이에 가져갈 5만 원대 선물을 찾고 있어.</div><div class="chat-assistant-message"><span class="chat-assistant-mark">${chatIcon("sparkle")}</span><div><strong>모아</strong><p>새로운 공간에 잘 어울리는 선물을 찾고 계시군요.<br>친구의 취향을 조금 더 알려주시면 함께 골라볼게요.</p><div class="chat-example-callout">${chatIcon("gift")}실용적인 선물과 감성적인 선물 중<br>어느 쪽을 더 좋아하나요?</div><p class="chat-sample-note">화면 구성을 보여주는 가상의 대화입니다.</p></div></div></div>
      </div>
      <div class="chat-composer-area"><p id="chat-error" class="chat-error" role="alert" hidden></p><form class="chat-composer" id="chat-preview-form"><label class="chat-sr-only" for="chat-prompt">쇼핑 도우미에게 물어볼 내용</label><textarea id="chat-prompt" rows="2" maxlength="2000" placeholder="어떤 상품을 찾고 있나요? 편하게 이야기해 주세요." aria-describedby="chat-privacy-note"></textarea><div class="chat-composer-tools"><div><button type="button" class="chat-icon-button" aria-label="파일 첨부 준비 중" disabled>${chatIcon("plus")}</button><span class="chat-composer-label">${chatIcon("sparkle")}모아 AI</span></div><button class="chat-send" type="submit" aria-label="메시지 전송">${chatIcon("arrow")}</button></div></form><p class="chat-composer-note" id="chat-privacy-note">질문과 최근 대화·공개 상품 정보가 Groq로 전송됩니다. 개인정보는 입력하지 마세요.<br>AI 답변은 부정확할 수 있습니다. 대화는 화면을 나가거나 새로고침하면 초기화됩니다.</p></div>
    </section></div>`;

  const input = root.querySelector("#chat-prompt");
  root.querySelector("#chat-privacy-note").firstChild.textContent = "질문·최근 대화·공개 상품 정보·검색된 참고 문서가 Groq로 전송됩니다. 개인정보는 입력하지 마세요.";
  const workspace = root.querySelector(".chat-workspace");
  const stage = root.querySelector(".chat-stage");
  const welcome = root.querySelector("#chat-welcome");
  const examplePanel = root.querySelector("#chat-example");
  const form = root.querySelector("#chat-preview-form");
  const send = root.querySelector(".chat-send");
  const errorNote = root.querySelector("#chat-error");
  const connection = root.querySelector("#chat-connection");
  const conversation = document.createElement("div");
  conversation.className = "chat-conversation";
  conversation.setAttribute("role", "log");
  conversation.setAttribute("aria-label", "모아와의 대화");
  conversation.setAttribute("aria-live", "polite");
  conversation.hidden = true;
  stage.append(conversation);
  let history = [];
  let pending = false;
  let controller = null;
  let generation = 0;
  let configured = false;
  send.disabled = true;
  const messageNode = (role, text, sources = []) => {
    const node = document.createElement("div");
    node.className = role === "user" ? "chat-user-message" : "chat-assistant-reply";
    const label = document.createElement("strong");
    label.textContent = role === "user" ? "나" : "모아";
    const content = document.createElement(role === "user" ? "p" : "div");
    if (role === "assistant") {
      content.className = "chat-markdown";
      // Only parser-generated markup is inserted. Raw HTML is escaped by markdown-it.
      content.innerHTML = chatMarkdown.render(text);
    } else {
      content.textContent = text;
    }
    node.append(label, content);
    if (role === "assistant" && sources.length) {
      const references = document.createElement("div");
      references.className = "chat-sources";
      const heading = document.createElement("strong");
      heading.textContent = "검색된 참고 문서";
      references.append(heading);
      sources.forEach(source => {
        const item = document.createElement("span");
        item.textContent = `[${source.id}] ${source.file} · ${source.start_line}–${source.end_line}행`;
        references.append(item);
      });
      node.append(references);
    }
    conversation.append(node);
    node.scrollIntoView({ block: "nearest", behavior: "smooth" });
    return node;
  };
  const reset = () => {
    generation += 1;
    controller?.abort();
    history = [];
    pending = false;
    input.disabled = false;
    send.disabled = !configured;
    form.removeAttribute("aria-busy");
    send.setAttribute("aria-label", "메시지 전송");
    conversation.replaceChildren();
    errorNote.hidden = true;
    input.value = "";
  };
  const setSidebar = (open) => {
    root.querySelector(".chat-workspace").classList.toggle("sidebar-open", open);
    root.querySelector(".chat-sidebar-toggle").setAttribute("aria-expanded", String(open));
    root.querySelector(".chat-backdrop").hidden = !open;
  };
  const showExample = (example) => {
    welcome.hidden = example || history.length > 0;
    examplePanel.hidden = !example;
    conversation.hidden = example || history.length === 0;
    stage.classList.toggle("has-conversation", !conversation.hidden);
    root.querySelectorAll(".chat-history-item").forEach(button => button.classList.toggle("active", example ? button.hasAttribute("data-chat-example") : button.hasAttribute("data-chat-home")));
    setSidebar(false);
  };
  root.querySelectorAll("[data-prompt]").forEach(button => button.addEventListener("click", () => { input.value = button.dataset.prompt; input.focus(); }));
  root.querySelectorAll("[data-chat-example]").forEach(button => button.addEventListener("click", () => showExample(true)));
  root.querySelectorAll("[data-chat-home], .chat-new").forEach(button => button.addEventListener("click", () => { reset(); showExample(false); }));
  root.querySelector(".chat-sidebar-toggle").addEventListener("click", () => setSidebar(true));
  root.querySelectorAll(".chat-sidebar-close, .chat-backdrop").forEach(button => button.addEventListener("click", () => setSidebar(false)));
  root.querySelector(".chat-workspace").addEventListener("keydown", event => { if (event.key === "Escape") { setSidebar(false); root.querySelector(".chat-sidebar-toggle").focus(); } });
  const ready = api("/api/chat/status").then(status => {
    if (!root.contains(workspace)) return;
    configured = status.configured;
    connection.textContent = configured ? "Groq · 연결 설정됨" : "API 키 설정 필요";
    connection.title = configured ? `모델: ${status.model} · 실제 연결은 전송 시 확인합니다.` : "서버 .env의 GROQ_API_KEY 설정 후 재시작하세요.";
    send.disabled = !configured;
    if (!configured) {
      errorNote.textContent = "AI 연결 전입니다. 서버에 GROQ_API_KEY를 설정한 뒤 재시작하세요. 대화 예시는 바로 확인할 수 있어요.";
      errorNote.hidden = false;
    }
  }).catch(() => {
    connection.textContent = "연결 상태 확인 실패";
    errorNote.textContent = "서버 연결 상태를 확인하지 못했습니다. 화면을 새로고침해 주세요.";
    errorNote.hidden = false;
  });
  form.addEventListener("submit", async event => {
    event.preventDefault();
    await ready;
    const prompt = input.value.trim();
    if (pending || !configured || !prompt || !root.contains(workspace)) return;
    if (prompt.length > 2000) { showToast("질문은 2,000자 이하로 입력해 주세요."); return; }
    const requestGeneration = ++generation;
    const previous = history.slice(-10);
    while (previous.length && previous.reduce((total, item) => total + item.content.length, 0) + prompt.length > 12000) previous.splice(0, 2);
    const messages = [...previous, { role: "user", content: prompt }];
    welcome.hidden = true;
    examplePanel.hidden = true;
    conversation.hidden = false;
    stage.classList.add("has-conversation");
    const userNode = messageNode("user", prompt);
    const waitingNode = messageNode("assistant", "답변을 준비하고 있어요…");
    waitingNode.classList.add("chat-waiting");
    pending = true;
    send.disabled = true;
    send.setAttribute("aria-label", "응답 대기 중");
    input.disabled = true;
    form.setAttribute("aria-busy", "true");
    errorNote.hidden = true;
    controller = new AbortController();
    const requestController = controller;
    const timeout = setTimeout(() => requestController.abort(), 35000);
    try {
      const result = await api("/api/chat", { ...requestOptions("POST", { messages }), signal: requestController.signal });
      if (requestGeneration !== generation || !root.contains(workspace)) return;
      waitingNode.remove();
      messageNode("assistant", result.reply, result.sources || []);
      history = [...messages, { role: "assistant", content: result.reply }];
      input.value = "";
    } catch (error) {
      if (requestGeneration !== generation || !root.contains(workspace)) return;
      waitingNode.remove();
      userNode.remove();
      errorNote.textContent = error.name === "AbortError" ? "응답 대기 시간이 초과되었습니다. 질문을 다시 전송해 주세요." : error.message;
      errorNote.hidden = false;
    } finally {
      clearTimeout(timeout);
      if (requestGeneration === generation && root.contains(workspace)) {
        pending = false;
        input.disabled = false;
        send.disabled = !configured;
        send.setAttribute("aria-label", "메시지 전송");
        form.removeAttribute("aria-busy");
        input.focus({ preventScroll: true });
      }
    }
  });
  input.addEventListener("keydown", event => {
    if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      form.requestSubmit();
    }
  });
}
