/**
 * motion.ts — Lenis 스무스 스크롤 + GSAP ScrollTrigger 모션 레이어.
 *
 * - Lenis: 문서 전체 스무스 스크롤 (싱글턴 — View Transitions 스왑에도 유지)
 * - ScrollTrigger.batch: `.reveal` 요소 순차 리빌 (기존 IntersectionObserver 대체)
 * - 히어로: `[data-hero-title] .hero-line-inner` 라인 마스크 리빌 + `.hero-sub` 페이드업
 * - 엔트리 페이지: `[data-entry-stagger]` 자식 순차 등장
 * - 카드: 포인터 추적 틸트 + 글레어 (hover+fine pointer에서만)
 * - `prefers-reduced-motion: reduce` → 전부 스킵, 콘텐츠 즉시 표시
 *
 * 상태 규약: 숨김 초기 상태는 CSS가 `.js` + `:not(.in-view)` 스코프로 관리.
 * 애니메이션 시작 시 `in-view`를 붙이고 GSAP이 from→to 를 구동, 끝나면 clearProps.
 */
import { gsap } from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import Lenis from 'lenis';

gsap.registerPlugin(ScrollTrigger);

const REDUCED = '(prefers-reduced-motion: reduce)';
const FINE_HOVER = '(hover: hover) and (pointer: fine)';

let lenis: Lenis | null = null;
let lenisTicker: ((time: number) => void) | null = null;
let cardCleanups: Array<() => void> = [];

function prefersReduced(): boolean {
  return window.matchMedia(REDUCED).matches;
}

/* ---------------------------------------------------------------- lenis */
function ensureLenis() {
  if (lenis || prefersReduced()) return;
  lenis = new Lenis({ lerp: 0.12, autoRaf: false });
  lenis.on('scroll', ScrollTrigger.update);
  lenisTicker = (time: number) => lenis?.raf(time * 1000);
  gsap.ticker.add(lenisTicker);
  gsap.ticker.lagSmoothing(0);
}

/* ----------------------------------------------------------- hero intro */
function initHero() {
  const title = document.querySelector<HTMLElement>('[data-hero-title]:not(.in-view)');
  if (title) {
    title.classList.add('in-view');
    const lines = title.querySelectorAll<HTMLElement>('.hero-line-inner');
    gsap.fromTo(
      lines,
      { yPercent: 112 },
      {
        yPercent: 0,
        duration: 1.1,
        ease: 'power4.out',
        stagger: 0.12,
        clearProps: 'transform',
      },
    );
  }
  const sub = document.querySelector<HTMLElement>('.hero-sub:not(.in-view)');
  if (sub) {
    sub.classList.add('in-view');
    gsap.fromTo(
      sub,
      { autoAlpha: 0, y: 24 },
      { autoAlpha: 1, y: 0, duration: 0.9, ease: 'power3.out', delay: 0.45, clearProps: 'all' },
    );
  }
}

/* ------------------------------------------------------- entry stagger */
function initEntryStagger() {
  const wrap = document.querySelector<HTMLElement>('[data-entry-stagger]:not(.in-view)');
  if (!wrap) return;
  wrap.classList.add('in-view');
  gsap.fromTo(
    wrap.children,
    { autoAlpha: 0, y: 26 },
    { autoAlpha: 1, y: 0, duration: 0.85, ease: 'power3.out', stagger: 0.09, clearProps: 'all' },
  );
}

/* ------------------------------------------------------- scroll reveal */
function initReveal() {
  const els = Array.from(document.querySelectorAll<HTMLElement>('.reveal:not(.in-view)'));
  if (!els.length) return;
  ScrollTrigger.batch(els, {
    start: 'top 88%',
    once: true,
    onEnter: (batch) => {
      batch.forEach((el) => el.classList.add('in-view'));
      gsap.fromTo(
        batch,
        { autoAlpha: 0, y: 30 },
        {
          autoAlpha: 1,
          y: 0,
          duration: 0.9,
          ease: 'power3.out',
          stagger: 0.08,
          overwrite: true,
          clearProps: 'all',
        },
      );
    },
  });
  // 배치가 못 잡는 케이스(짧은 페이지 하단 등) 안전망
  ScrollTrigger.refresh();
}

/* ---------------------------------------------------------- card tilt */
function initCardTilt() {
  if (!window.matchMedia(FINE_HOVER).matches) return;
  document.querySelectorAll<HTMLElement>('.media-card').forEach((card) => {
    const cover = card.querySelector<HTMLElement>('.cover');
    if (!cover) return;
    const rx = gsap.quickTo(cover, 'rotationX', { duration: 0.5, ease: 'power3.out' });
    const ry = gsap.quickTo(cover, 'rotationY', { duration: 0.5, ease: 'power3.out' });
    gsap.set(cover, { transformPerspective: 700 });

    const move = (e: PointerEvent) => {
      const r = cover.getBoundingClientRect();
      const px = (e.clientX - r.left) / r.width; // 0..1
      const py = (e.clientY - r.top) / r.height;
      ry(gsap.utils.clamp(-5, 5, (px - 0.5) * 10));
      rx(gsap.utils.clamp(-5, 5, (0.5 - py) * 10));
      cover.style.setProperty('--mx', `${px * 100}%`);
      cover.style.setProperty('--my', `${py * 100}%`);
    };
    const leave = () => {
      rx(0);
      ry(0);
    };
    card.addEventListener('pointermove', move);
    card.addEventListener('pointerleave', leave);
    cardCleanups.push(() => {
      card.removeEventListener('pointermove', move);
      card.removeEventListener('pointerleave', leave);
    });
  });
}

/* -------------------------------------------------------------- public */
export function initMotion() {
  if (prefersReduced()) {
    // 모션 없이 전부 표시 (CSS reduced-motion 블록과 이중 안전망)
    document
      .querySelectorAll<HTMLElement>('[data-hero-title], .hero-sub, .reveal, [data-entry-stagger]')
      .forEach((el) => el.classList.add('in-view'));
    return;
  }
  ensureLenis();
  initHero();
  initEntryStagger();
  initReveal();
  initCardTilt();
}

export function destroyMotion() {
  ScrollTrigger.getAll().forEach((st) => st.kill());
  cardCleanups.forEach((fn) => fn());
  cardCleanups = [];
  // Lenis 는 window 레벨 싱글턴으로 유지 — body 스왑과 무관
}
