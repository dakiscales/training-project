"use strict";

// Python owns questions, correct answers, and scoring. This file owns the screen.
(() => {
  const $ = (id) => document.getElementById(id);
  const choices = ["A", "B", "C", "D"];
  const state = {
    view: "home", topics: [], quiz: null, index: 0, answers: new Map(),
    busy: false, expired: false, lastTopic: null, controller: null, requestId: 0,
  };

  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function announce(message) { $("announcement").textContent = message; }

  function showView(view, focusId) {
    state.view = view;
    for (const name of ["home", "loading", "quiz", "results"]) {
      $(`${name}-view`).hidden = name !== view;
    }
    window.scrollTo({ top: 0, behavior: "instant" });
    if (focusId) $(focusId).focus({ preventScroll: true });
  }

  function cancelRequest() {
    state.requestId += 1;
    state.controller?.abort();
    state.controller = null;
  }

  // A timeout frees the interface. Leaving a screen also cancels its request,
  // so a late response cannot replace the screen the player chose.
  async function request(path, options = {}) {
    cancelRequest();
    const requestId = state.requestId;
    const controller = new AbortController();
    state.controller = controller;
    let timedOut = false;
    const timeout = setTimeout(() => { timedOut = true; controller.abort(); }, 12000);
    try {
      const response = await fetch(path, {
        ...options, signal: controller.signal, cache: "no-store",
        headers: { Accept: "application/json", ...options.headers },
      });
      const data = await response.json().catch(() => null);
      if (requestId !== state.requestId) throw new Error("Cancelled");
      if (!response.ok) {
        const error = new Error(
          typeof data?.detail === "string" ? data.detail : "The server could not complete this request."
        );
        error.status = response.status;
        throw error;
      }
      if (data === null) throw new Error("The server sent an unreadable response. Please try again.");
      return data;
    } catch (error) {
      if (requestId !== state.requestId) {
        error.cancelled = true;
      } else if (timedOut) {
        error.message = "The server took too long to respond. Please try again.";
      } else if (error instanceof TypeError) {
        error.message = "We couldn't connect to the quiz server. Check your connection and try again.";
      }
      throw error;
    } finally {
      clearTimeout(timeout);
      if (requestId === state.requestId) state.controller = null;
    }
  }

  const validText = (value) => typeof value === "string" && value.trim().length > 0;
  const validId = (value) => Number.isSafeInteger(value) && value > 0;
  const validSlug = (value) => typeof value === "string" && /^[a-z]+(?:-[a-z]+)*$/.test(value) && value.length <= 32;

  function validateTopics(data) {
    if (!Array.isArray(data?.topics) || !data.topics.every((topic) =>
      topic && validSlug(topic.slug) && validText(topic.name) && typeof topic.description === "string" &&
      validId(topic.quiz_version) && Number.isInteger(topic.question_count) && topic.question_count >= 0
    ) || new Set(data.topics.map((topic) => topic.slug)).size !== data.topics.length) {
      throw new Error("The topic list couldn't be read. Please try again.");
    }
    return data.topics;
  }

  function validateQuiz(quiz, slug) {
    if (quiz?.topic_slug !== slug || !validText(quiz.topic_name) || !validId(quiz.quiz_version) ||
      quiz.question_count !== 5 || !Array.isArray(quiz.questions) || quiz.questions.length !== 5 ||
      !quiz.questions.every((q) => q && validId(q.question_id) && validText(q.prompt) &&
        Array.isArray(q.options) && q.options.length === 4 &&
        q.options.every((option) => option && choices.includes(option.key) && validText(option.text)) &&
        new Set(q.options.map((option) => option.key)).size === 4) ||
      new Set(quiz.questions.map((q) => q.question_id)).size !== 5) {
      throw new Error("This quiz isn't ready to play yet. Please try again later.");
    }
    return quiz;
  }

  function validateResults(data) {
    const quiz = state.quiz;
    if (data?.topic_slug !== quiz.topic_slug || data.quiz_version !== quiz.quiz_version ||
      data.total !== quiz.question_count || !Number.isInteger(data.score) ||
      data.score < 0 || data.score > data.total || !Number.isFinite(data.percentage) ||
      data.percentage < 0 || data.percentage > 100 || !Array.isArray(data.results) ||
      data.results.length !== quiz.question_count ||
      !data.results.every((row) => row && validId(row.question_id)) ||
      new Set(data.results.map((r) => r.question_id)).size !== quiz.question_count ||
      !data.results.every((r) => state.answers.has(r.question_id) &&
        r.selected_option === state.answers.get(r.question_id) && choices.includes(r.correct_option) &&
        typeof r.is_correct === "boolean" && validText(r.explanation))) {
      throw new Error("We couldn't read your score. Your answers are still here; please try submitting again.");
    }
    return data;
  }

  // Decorative SVGs are local artwork, not quiz data or answer keys.
  const artwork = {
    space: '<ellipse cx="85" cy="61" rx="67" ry="20" transform="rotate(-25 85 61)" fill="none" stroke="#a94c60" stroke-width="1.5"/><circle cx="85" cy="61" r="34" fill="#783348" stroke="currentColor" stroke-width="1.5"/><path d="M58 41c16 12 34 18 52 18M53 61c21 15 37 21 58 20" fill="none" stroke="#a24a60" stroke-width="2"/><path d="M24 84c13 7 46 0 73-13s47-29 47-35" fill="none" stroke="#ffaca9" stroke-width="3"/><path d="M137 17v12m-6-6h12M26 30v8m-4-4h8" stroke="currentColor" stroke-width="1.5"/><circle cx="130" cy="96" r="2.5" fill="#ff625c"/>',
    maths: '<g transform="rotate(-12 58 65)"><rect x="21" y="30" width="64" height="64" rx="10" fill="#502b3c" stroke="#a35870"/><path d="M41 62h24M53 50v24" stroke="#ffb1ab" stroke-width="4" stroke-linecap="round"/></g><g transform="rotate(12 118 59)"><rect x="84" y="20" width="64" height="64" rx="10" fill="#81364a" stroke="#f18a90"/><path d="m105 43 23 22m0-22-23 22" stroke="#ffc4b8" stroke-width="4" stroke-linecap="round"/></g><path d="M128 98h17m-17 7h17M24 13v10m-5-5h10" stroke="#ff888c" stroke-width="2"/>',
    web: '<g transform="rotate(-6 85 62)"><rect x="27" y="24" width="118" height="78" rx="8" fill="#502938" stroke="#d07588" stroke-width="1.5"/><path d="M28 43h116" stroke="#d07588"/><g fill="#ed919b"><circle cx="37" cy="34" r="2"/><circle cx="45" cy="34" r="2"/><circle cx="53" cy="34" r="2"/></g><path d="m65 59-13 12 13 12m42-24 13 12-13 12m-15-29-12 34" fill="none" stroke="#ffb1ab" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/></g><path d="m136 85 21 14-11 1-4 11z" fill="#ff625c" stroke="#ffb1ab"/><path d="M25 10v11m-5-6h10" stroke="#d07588" stroke-width="1.5"/>',
    default: '<rect x="48" y="16" width="76" height="94" rx="12" transform="rotate(-10 85 62)" fill="#81364a" stroke="currentColor"/><path d="M73 45c0-18 31-18 31 0 0 13-17 12-17 24" fill="none" stroke="#ffc4b8" stroke-width="5" stroke-linecap="round"/><circle cx="87" cy="83" r="3" fill="#ffc4b8"/>',
  };

  function renderTopics() {
    $("topic-grid").replaceChildren();
    state.topics.forEach((topic, index) => {
      const card = element("button", "topic-card");
      card.type = "button";
      card.setAttribute("aria-label", `Play ${topic.name}, ${topic.question_count} questions`);
      const art = element("span", "topic-art");
      art.setAttribute("aria-hidden", "true");
      const drawing = Object.hasOwn(artwork, topic.slug) ? artwork[topic.slug] : artwork.default;
      art.innerHTML = `<svg viewBox="0 0 172 120" fill="none" xmlns="http://www.w3.org/2000/svg">${drawing}</svg>`;
      art.append(element("span", "topic-index", String(index + 1).padStart(2, "0")));
      const copy = element("span", "topic-copy");
      copy.append(element("span", "topic-meta", `${topic.question_count} questions · No timer`),
        element("span", "topic-name", topic.name), element("span", "topic-description", topic.description));
      const start = element("span", "topic-start", "Let's play");
      const arrow = element("span", "", "↗");
      arrow.setAttribute("aria-hidden", "true");
      start.append(arrow);
      copy.append(start);
      card.append(art, copy);
      card.addEventListener("click", () => loadQuiz(topic.slug));
      $("topic-grid").append(card);
    });
    $("topic-count").textContent = `${state.topics.length} ${state.topics.length === 1 ? "topic" : "topics"} to explore`;
  }

  async function loadTopics() {
    $("topic-grid").setAttribute("aria-busy", "true");
    $("topics-notice").hidden = false;
    $("topics-notice").classList.remove("notice-error");
    $("topics-message").textContent = "Finding your next quiz…";
    $("retry-topics").hidden = true;
    try {
      state.topics = validateTopics(await request("/topics"));
      renderTopics();
      $("topics-notice").hidden = state.topics.length > 0;
      if (state.topics.length === 0) {
        $("topics-message").textContent = "No topics are available yet. Check back soon.";
        $("retry-topics").hidden = false;
      }
      announce(`${state.topics.length} quiz topics available.`);
    } catch (error) {
      if (error.cancelled) return;
      $("topics-notice").classList.add("notice-error");
      $("topics-message").textContent = error.message;
      $("retry-topics").hidden = false;
      $("topic-count").textContent = "Topics unavailable";
    } finally {
      $("topic-grid").setAttribute("aria-busy", "false");
    }
  }

  async function loadQuiz(slug) {
    state.lastTopic = slug;
    state.busy = false;
    state.expired = false;
    $("loading-title").textContent = "Getting your quiz ready.";
    $("loading-message").textContent = "Loading questions…";
    $("loading-symbol").hidden = false;
    $("retry-quiz").hidden = true;
    showView("loading", "loading-title");
    try {
      const quiz = validateQuiz(await request(`/quizzes/${encodeURIComponent(slug)}`), slug);
      state.quiz = quiz;
      state.index = 0;
      state.answers.clear();
      $("quiz-error").hidden = true;
      $("reload-quiz").hidden = true;
      $("quiz-topic").textContent = quiz.topic_name;
      document.title = `${quiz.topic_name} · nejya guessing`;
      renderQuestion();
      showView("quiz", "question-title");
      announce(`${quiz.topic_name} quiz ready. Five questions.`);
    } catch (error) {
      if (error.cancelled) return;
      $("loading-title").textContent = "Couldn't load this quiz.";
      $("loading-message").textContent = error.message;
      $("loading-symbol").hidden = true;
      $("retry-quiz").hidden = false;
      $("loading-title").focus();
    }
  }

  function renderProgress() {
    $("question-steps").replaceChildren();
    state.quiz.questions.forEach((q, index) => {
      const answered = state.answers.has(q.question_id);
      const button = element("button", `question-step${answered ? " answered" : ""}`, String(index + 1));
      button.type = "button";
      button.disabled = state.busy;
      button.setAttribute("aria-label", `Question ${index + 1}, ${answered ? "answered" : "unanswered"}`);
      if (index === state.index) button.setAttribute("aria-current", "step");
      button.addEventListener("click", () => { state.index = index; renderQuestion(true); });
      $("question-steps").append(button);
    });
    $("answered-count").textContent = `${state.answers.size} of ${state.quiz.question_count} answered`;
    $("quiz-progress").max = state.quiz.question_count;
    $("quiz-progress").value = state.answers.size;
  }

  function updateControls() {
    const last = state.index === state.quiz.questions.length - 1;
    const selected = state.answers.has(state.quiz.questions[state.index].question_id);
    const complete = state.answers.size === state.quiz.question_count;
    $("question-fieldset").disabled = state.busy || state.expired;
    $("previous-question").disabled = state.index === 0 || state.busy;
    $("next-question").disabled = state.busy || state.expired || (last ? !complete : !selected);
    $("next-question").textContent = state.busy ? "Checking answers…" : last ? "See my results ↗" : "Next question →";
    $("question-help").textContent = state.expired ? "Reload this quiz to play its latest version."
      : last && !complete ? "Answer all five questions to see your score. Use the numbers to go back."
      : "You can change any answer before submitting.";
    $("quiz-form").setAttribute("aria-busy", String(state.busy));
  }

  function renderQuestion(focus = false) {
    const question = state.quiz.questions[state.index];
    $("question-position").textContent = `QUESTION ${String(state.index + 1).padStart(2, "0")} / ${String(state.quiz.question_count).padStart(2, "0")}`;
    $("question-title").textContent = question.prompt;
    $("options").replaceChildren();
    question.options.forEach((option) => {
      const label = element("label", "option");
      const input = element("input");
      input.type = "radio";
      input.name = `question-${question.question_id}`;
      input.value = option.key;
      input.checked = state.answers.get(question.question_id) === option.key;
      input.setAttribute("aria-describedby", "question-hint");
      input.addEventListener("change", () => {
        state.answers.set(question.question_id, option.key);
        if (!state.expired) $("quiz-error").hidden = true;
        renderProgress();
        updateControls();
      });
      const letter = element("span", "option-letter", option.key);
      const check = element("span", "option-check", "✓");
      check.setAttribute("aria-hidden", "true");
      label.append(input, letter, element("span", "option-text", option.text), check);
      $("options").append(label);
    });
    renderProgress();
    updateControls();
    if (focus) $("question-title").focus({ preventScroll: false });
  }

  async function submitQuiz() {
    if (state.busy || state.expired || state.answers.size !== state.quiz.question_count) return;
    state.busy = true;
    $("quiz-error").hidden = true;
    renderProgress();
    updateControls();
    announce("Checking your answers…");
    try {
      const result = validateResults(await request("/submissions", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          topic_slug: state.quiz.topic_slug,
          quiz_version: state.quiz.quiz_version,
          answers: state.quiz.questions.map((q) => ({
            question_id: q.question_id, selected_option: state.answers.get(q.question_id),
          })),
        }),
      }));
      state.busy = false;
      if ($("leave-dialog").open) $("leave-dialog").close("stay");
      renderResults(result);
    } catch (error) {
      if (error.cancelled) return;
      state.busy = false;
      announce("");
      state.expired = error.status === 409 || error.status === 404;
      $("quiz-error-message").textContent = state.expired ? `${error.message} Reloading clears this round's answers.`
        : `${error.message} Your answers have been kept. You can submit again.`;
      $("quiz-error").hidden = false;
      $("reload-quiz").hidden = !state.expired;
      renderProgress();
      updateControls();
    }
  }

  function renderResults(result) {
    $("results-topic").textContent = state.quiz.topic_name;
    $("score-value").textContent = String(result.score);
    $("score-total").textContent = ` / ${result.total}`;
    $("score-percentage").textContent = `${result.percentage}% correct`;
    $("results-title").textContent = result.score === result.total ? "You knew your stuff." : result.score === 0 ? "Curiosity wins." : "Look at you go.";
    $("results-message").textContent = result.score === result.total ? "A perfect round. Nicely done. Keep that curiosity going with another topic."
      : "Every guess is a chance to learn. Take a look at the answers below and give it another go.";
    $("review-list").replaceChildren();
    const byId = new Map(result.results.map((row) => [row.question_id, row]));
    state.quiz.questions.forEach((question, index) => {
      const row = byId.get(question.question_id);
      const item = element("li", "review-item");
      const number = element("span", "review-number", String(index + 1).padStart(2, "0"));
      number.setAttribute("aria-hidden", "true");
      const body = element("div");
      const top = element("div", "review-topline");
      top.append(element("h3", "", question.prompt), element("span", `review-status${row.is_correct ? "" : " incorrect"}`, row.is_correct ? "✓ Correct" : "✕ Incorrect"));
      body.append(top);
      const answerText = (key) => `${key} — ${question.options.find((option) => option.key === key).text}`;
      const selected = element("p", "review-answer", "Your answer: ");
      selected.append(element("strong", "", answerText(row.selected_option)));
      body.append(selected);
      if (!row.is_correct) {
        const correct = element("p", "review-answer", "Correct answer: ");
        correct.append(element("strong", "", answerText(row.correct_option)));
        body.append(correct);
      }
      body.append(element("p", "review-explanation", row.explanation));
      item.append(number, body);
      $("review-list").append(item);
    });
    document.title = `${result.score}/${result.total} · nejya guessing`;
    showView("results", "results-title");
    announce(`Quiz complete. You scored ${result.score} out of ${result.total}.`);
  }

  function goHome() {
    cancelRequest();
    state.quiz = null;
    state.answers.clear();
    state.busy = false;
    state.expired = false;
    document.title = "nejya guessing";
    showView("home", "topics-title");
    announce("Choose a topic to begin.");
    if (state.topics.length === 0) loadTopics();
  }

  document.querySelectorAll("[data-home]").forEach((button) => {
    button.addEventListener("click", (event) => {
      event.preventDefault();
      if (state.view === "quiz" && state.answers.size > 0) $("leave-dialog").showModal();
      else goHome();
    });
  });
  $("leave-dialog").addEventListener("close", () => {
    if ($("leave-dialog").returnValue === "leave") goHome();
    $("leave-dialog").returnValue = "";
  });
  $("quiz-form").addEventListener("submit", (event) => {
    event.preventDefault();
    if (state.busy || state.expired || !state.answers.has(state.quiz.questions[state.index].question_id)) return;
    if (state.index < state.quiz.questions.length - 1) {
      state.index += 1;
      renderQuestion(true);
    } else submitQuiz();
  });
  $("previous-question").addEventListener("click", () => {
    if (state.index > 0 && !state.busy) { state.index -= 1; renderQuestion(true); }
  });
  $("retry-topics").addEventListener("click", loadTopics);
  $("retry-quiz").addEventListener("click", () => loadQuiz(state.lastTopic));
  $("reload-quiz").addEventListener("click", () => loadQuiz(state.quiz.topic_slug));
  $("play-again").addEventListener("click", () => loadQuiz(state.quiz.topic_slug));
  loadTopics();
})();
