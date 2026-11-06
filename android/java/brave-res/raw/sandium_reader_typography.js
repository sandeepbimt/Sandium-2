// ==UserScript==
// @name         Universal - Reader Typography
// @namespace    Quetta
// @version      4.0
// @description  Reader-style typography with adaptive justified text
// @match        *://*/*
// @run-at       document-end
// ==/UserScript==

(function () {
    'use strict';

    const STYLE_ID = 'quetta-reader-typography-v4';
    const CLASS_NAME = 'quetta-reader-paragraph';

    const CSS = \`
        .\${CLASS_NAME} {
            font-size: clamp(0.97rem, 4vw, 1.06rem) !important;
            line-height: 1.58 !important;
            text-align: justify !important;
            text-wrap: pretty !important;
            hyphens: auto !important;
            -webkit-hyphens: auto !important;
            word-spacing: normal !important;
            letter-spacing: normal !important;
        }
        .\${CLASS_NAME} {
            text-wrap: pretty;
        }
    \`;

    const EXCLUDED = [
        'nav', 'header', 'footer', 'aside', 'form', 'button',
        'textarea', 'input', 'select', 'figure',
        '[role="navigation"]', '[role="button"]',
        '[contenteditable="true"]', '[aria-hidden="true"]',
        '.comments', '#comments'
    ].join(',');

    function validParagraph(p) {
        if (!p || p.closest(EXCLUDED)) return false;
        const text = (p.innerText || '').trim();
        if (text.length < 80) return false;
        const rect = p.getBoundingClientRect();
        return rect.width >= 280 && rect.height >= 10;
    }

    function findArticle() {
        const paragraphs = [...document.querySelectorAll('p')].filter(validParagraph);
        if (paragraphs.length < 3) return null;
        const candidates = new Map();
        for (const p of paragraphs) {
            let el = p.parentElement;
            for (let i = 0; i < 7 && el; i++) {
                candidates.set(el, (candidates.get(el) || 0) + 1);
                el = el.parentElement;
            }
        }
        let best = null;
        let bestScore = -Infinity;
        for (const [el, count] of candidates) {
            if (count < 3) continue;
            const rect = el.getBoundingClientRect();
            if (rect.width < 280) continue;
            const widthPenalty = Math.abs(Math.min(rect.width, 850) - 650);
            const score = count * 1000 - widthPenalty;
            if (score > bestScore) {
                bestScore = score;
                best = el;
            }
        }
        return best;
    }

    function injectCSS() {
        if (document.getElementById(STYLE_ID)) return;
        const style = document.createElement('style');
        style.id = STYLE_ID;
        style.textContent = CSS;
        document.head.appendChild(style);
    }

    function apply(container) {
        if (!container) return;
        injectCSS();
        container.querySelectorAll('p').forEach(p => {
            if (validParagraph(p)) p.classList.add(CLASS_NAME);
        });
    }

    let articleFound = false;
    let observer = null;
    let attempts = 0;

    function detect() {
        if (articleFound) return;
        const article = findArticle();
        if (!article) return;
        apply(article);
        articleFound = true;
        if (observer) {
            observer.disconnect();
            observer = null;
        }
    }

    detect();

    if (!articleFound) {
        observer = new MutationObserver(() => {
            attempts++;
            detect();
            if (attempts >= 25 && observer) {
                observer.disconnect();
                observer = null;
            }
        });
        observer.observe(document.documentElement, { childList: true, subtree: true });
        setTimeout(() => {
            if (observer) {
                observer.disconnect();
                observer = null;
            }
        }, 10000);
    }
})();
