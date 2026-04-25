/**
 * Simple i18n system for HITS.
 * Stores language preference in localStorage.
 * Uses a Svelte-writable-compatible store for reactivity.
 * Usage: import { t, locale } from '../lib/i18n';
 */

export type Locale = 'ko' | 'en';

const translations: Record<Locale, Record<string, string>> = {
  en: {
    // Common
    'app.title': 'HITS',
    'app.subtitle': 'Hybrid Intel Trace System',
    'loading': 'Loading...',
    'save': 'Save',
    'cancel': 'Cancel',
    'delete': 'Delete',
    'edit': 'Edit',
    'add': 'Add',
    'refresh': 'Refresh',
    'close': 'Close',
    'search': 'Search...',
    'copy': 'Copy',
    'copied': 'Copied to clipboard',

    // Auth
    'auth.login': 'Login',
    'auth.register': 'Create Account',
    'auth.username': 'Username',
    'auth.password': 'Password',
    'auth.confirmPassword': 'Confirm Password',
    'auth.passwordMin': 'Password must be at least 8 characters',
    'auth.passwordMismatch': 'Passwords do not match',
    'auth.loginFailed': 'Login failed',
    'auth.registerFailed': 'Registration failed',
    'auth.processing': 'Processing...',
    'auth.firstAccount': 'First account will be set as admin',
    'auth.hasAccount': 'Already have an account?',
    'auth.noAccount': 'Create new account',
    'auth.changePassword': 'Change Password',
    'auth.currentPassword': 'Current Password',
    'auth.newPassword': 'New Password',
    'auth.newPasswordConfirm': 'Confirm New Password',
    'auth.passwordChanged': 'Password changed',
    'auth.changeFailed': 'Failed to change password',
    'auth.logout': 'Logout',
    'auth.wrongPassword': 'Invalid current password',

    // Header
    'header.projects': 'Projects',
    'header.knowledge': 'Knowledge Tree',
    'header.timeline': 'Timeline',
    'header.handover': 'Handover',
    'header.toggleSidebar': 'Toggle sidebar',
    'header.refresh': 'Refresh',
    'header.admin': 'Admin',

    // Sidebar
    'sidebar.noProjects': 'No projects recorded',

    // Knowledge
    'knowledge.title': 'Knowledge Tree',
    'knowledge.addCategory': '+ Category',
    'knowledge.noCategories': 'No categories',
    'knowledge.createCategory': 'Create category',
    'knowledge.editCategory': 'Edit category',
    'knowledge.categoryName': 'Category name',
    'knowledge.categoryIcon': 'Icon',
    'knowledge.addedNode': 'Node added',
    'knowledge.editNode': 'Edit node',
    'knowledge.newNode': 'New node',
    'knowledge.nodeName': 'Name',
    'knowledge.nodeLayer': 'Layer',
    'knowledge.layerWhy': 'WHY (Intent)',
    'knowledge.layerHow': 'HOW (Logic)',
    'knowledge.layerWhat': 'WHAT (Execution)',
    'knowledge.nodeType': 'Action type',
    'knowledge.typeUrl': 'URL',
    'knowledge.typeShell': 'Shell command',
    'knowledge.nodeAction': 'Action',
    'knowledge.negativePath': 'Negative Path (failure route)',
    'knowledge.confirmDeleteCategory': 'Delete category and all nodes?',
    'knowledge.confirmDeleteNode': 'Delete this node?',
    'knowledge.saving': 'Saving...',

    // Timeline
    'timeline.title': 'Timeline',
    'timeline.addLog': '+ Record',
    'timeline.noLogs': 'No work logs',
    'timeline.createLog': 'Record work',
    'timeline.today': 'Today',
    'timeline.yesterday': 'Yesterday',
    'timeline.editLog': 'Edit work log',
    'timeline.newLog': 'New work log',
    'timeline.summary': 'What did you do?',
    'timeline.context': 'Details, decisions',
    'timeline.performer': 'Performer',
    'timeline.tags': 'Tags (comma separated)',
    'timeline.confirmDelete': 'Delete this work log?',
    'timeline.allProjects': 'All projects',

    // Performers
    'performer.manual': 'Manual',
    'performer.opencode': 'OpenCode',
    'performer.claude': 'Claude',
    'performer.cursor': 'Cursor',
    'performer.copilot': 'Copilot',

    // Handover
    'handover.title': 'Handover',
    'handover.selectProject': 'Select a project from the sidebar',
    'handover.noData': 'No handover data',
    'handover.sessionHistory': 'Session History',
    'handover.keyDecisions': 'Key Decisions',
    'handover.pendingItems': 'Pending / Follow-up',
    'handover.filesModified': 'Files Modified',
    'handover.recentWork': 'Recent Work',
    'handover.more': 'more',
    'handover.noProject': 'Select project',

    // Empty states
    'empty.noData': '(No data)',

    // Resume
    'resume.title': 'Resume',
    'resume.history': 'History',
    'resume.selectProject': 'Select a project from the sidebar',
    'resume.resumeWork': 'Resume Work',
    'resume.noPurpose': 'No purpose set',
    'resume.noState': 'No state recorded',
    'resume.noCheckpoint': 'No checkpoint available. Use hits_auto_checkpoint() at session end.',
    'resume.checkpointHistory': 'Checkpoint History',
    'resume.noCheckpoints': 'No checkpoints found.',
    'resume.nextSteps': 'Next Steps',
    'resume.mustKnow': 'Must Know',
    'resume.decisions': 'Decisions',
    'resume.blockers': 'Blockers',
    'resume.workaround': 'Workaround',
    'resume.files': 'Files',
    'resume.pendingSignals': 'Pending Signals',
    'resume.sessionHistory': 'Session History',
    'resume.recentWork': 'Recent Work',
    'resume.noDataAvailable': 'No data available',
    'resume.copy': 'Copy',
    'resume.copyPrompt': 'Prompt copied — open {tool} and paste',
    'resume.signalSent': 'Signal sent + prompt copied — open {tool} and paste',
    'resume.nextStepsGuide': 'Next steps:',
    'resume.guide1': 'Open your AI tool (Claude Code / OpenCode)',
    'resume.guide2': 'Paste the copied prompt into the chat',
    'resume.guide3': 'The AI will read the checkpoint and continue work',
    'resume.closeGuide': 'Close guide',
    'resume.hookSetup': 'First time? Set up auto-resume hooks',
    'resume.hookDesc': 'Connect once — then resume is automatic every time you start your AI tool.',

    // Timeline detail
    'timeline.files': 'Files',
    'timeline.commands': 'Commands',
    'timeline.saveFailed': 'Save failed',

    // Common extras
    'common.switchLang': 'Switch language',
    'app.loading': 'HITS...',
  },

  ko: {
    // Common
    'app.title': 'HITS',
    'app.subtitle': 'Hybrid Intel Trace System',
    'loading': '로딩 중...',
    'save': '저장',
    'cancel': '취소',
    'delete': '삭제',
    'edit': '편집',
    'add': '추가',
    'refresh': '새로고침',
    'close': '닫기',
    'search': '검색...',
    'copy': '복사',
    'copied': '클립보드에 복사되었습니다',

    // Auth
    'auth.login': '로그인',
    'auth.register': '계정 생성',
    'auth.username': '사용자명',
    'auth.password': '비밀번호',
    'auth.confirmPassword': '비밀번호 확인',
    'auth.passwordMin': '비밀번호는 8자 이상이어야 합니다',
    'auth.passwordMismatch': '비밀번호가 일치하지 않습니다',
    'auth.loginFailed': '로그인 실패',
    'auth.registerFailed': '회원가입 실패',
    'auth.processing': '처리 중...',
    'auth.firstAccount': '첫 번째 계정이 관리자로 설정됩니다',
    'auth.hasAccount': '이미 계정이 있으신가요?',
    'auth.noAccount': '새 계정 만들기',
    'auth.changePassword': '비밀번호 변경',
    'auth.currentPassword': '현재 비밀번호',
    'auth.newPassword': '새 비밀번호',
    'auth.newPasswordConfirm': '새 비밀번호 확인',
    'auth.passwordChanged': '비밀번호가 변경되었습니다',
    'auth.changeFailed': '비밀번호 변경 실패',
    'auth.logout': '로그아웃',
    'auth.wrongPassword': '현재 비밀번호가 틀립니다',

    // Header
    'header.projects': '프로젝트',
    'header.knowledge': '지식 트리',
    'header.timeline': '타임라인',
    'header.handover': '인수인계',
    'header.toggleSidebar': '사이드바 토글',
    'header.refresh': '새로고침',
    'header.admin': '관리자',

    // Sidebar
    'sidebar.noProjects': '기록된 프로젝트가 없습니다',

    // Knowledge
    'knowledge.title': '지식 트리',
    'knowledge.addCategory': '+ 카테고리',
    'knowledge.noCategories': '카테고리가 없습니다',
    'knowledge.createCategory': '카테고리 만들기',
    'knowledge.editCategory': '카테고리 편집',
    'knowledge.categoryName': '카테고리 이름',
    'knowledge.categoryIcon': '아이콘',
    'knowledge.addedNode': '노드 추가',
    'knowledge.editNode': '노드 편집',
    'knowledge.newNode': '새 노드',
    'knowledge.nodeName': '이름',
    'knowledge.nodeLayer': '계층',
    'knowledge.layerWhy': 'WHY (의도)',
    'knowledge.layerHow': 'HOW (방법)',
    'knowledge.layerWhat': 'WHAT (실행)',
    'knowledge.nodeType': '실행 유형',
    'knowledge.typeUrl': 'URL',
    'knowledge.typeShell': 'Shell 명령',
    'knowledge.nodeAction': '실행 내용',
    'knowledge.negativePath': '실패 경로 (Negative Path)',
    'knowledge.confirmDeleteCategory': '카테고리와 모든 노드를 삭제하시겠습니까?',
    'knowledge.confirmDeleteNode': '이 노드를 삭제하시겠습니까?',
    'knowledge.saving': '저장 중...',

    // Timeline
    'timeline.title': '타임라인',
    'timeline.addLog': '+ 기록',
    'timeline.noLogs': '작업 기록이 없습니다',
    'timeline.createLog': '작업 기록하기',
    'timeline.today': '오늘',
    'timeline.yesterday': '어제',
    'timeline.editLog': '작업 기록 편집',
    'timeline.newLog': '새 작업 기록',
    'timeline.summary': '무엇을 했나요?',
    'timeline.context': '상세 내용, 결정 사항',
    'timeline.performer': '수행자',
    'timeline.tags': '태그 (콤마로 구분)',
    'timeline.confirmDelete': '이 작업 기록을 삭제하시겠습니까?',
    'timeline.allProjects': '전체 프로젝트',

    // Performers
    'performer.manual': '수동',
    'performer.opencode': 'OpenCode',
    'performer.claude': 'Claude',
    'performer.cursor': 'Cursor',
    'performer.copilot': 'Copilot',

    // Handover
    'handover.title': '인수인계',
    'handover.selectProject': '좌측 사이드바에서 프로젝트를 선택하세요',
    'handover.noData': '인수인계 데이터가 없습니다',
    'handover.sessionHistory': '작업 이력',
    'handover.keyDecisions': '주요 결정 사항',
    'handover.pendingItems': '미완료 / 후속 작업',
    'handover.filesModified': '수정된 파일',
    'handover.recentWork': '최근 작업',
    'handover.more': '더 보기',
    'handover.noProject': '프로젝트 선택',

    // Empty states
    'empty.noData': '(데이터 없음)',

    // Resume
    'resume.title': '이어서 작업',
    'resume.history': '기록',
    'resume.selectProject': '좌측 사이드바에서 프로젝트를 선택하세요',
    'resume.resumeWork': '이어서 작업하기',
    'resume.noPurpose': '목표가 설정되지 않았습니다',
    'resume.noState': '상태가 기록되지 않았습니다',
    'resume.noCheckpoint': '체크포인트가 없습니다. 세션 종료 시 hits_auto_checkpoint()를 사용하세요.',
    'resume.checkpointHistory': '체크포인트 기록',
    'resume.noCheckpoints': '체크포인트가 없습니다.',
    'resume.nextSteps': '다음 단계',
    'resume.mustKnow': '필수 정보',
    'resume.decisions': '결정 사항',
    'resume.blockers': '차단 요소',
    'resume.workaround': '우회 방법',
    'resume.files': '파일',
    'resume.pendingSignals': '대기 중인 시그널',
    'resume.sessionHistory': '작업 이력',
    'resume.recentWork': '최근 작업',
    'resume.noDataAvailable': '데이터 없음',
    'resume.copy': '복사',
    'resume.copyPrompt': '프롬프트 복사됨 — {tool}을 열고 붙여넣으세요',
    'resume.signalSent': '시그널 전송 + 프롬프트 복사됨 — {tool}을 열고 붙여넣으세요',
    'resume.nextStepsGuide': '다음 단계:',
    'resume.guide1': 'AI 도구를 엽니다 (Claude Code / OpenCode)',
    'resume.guide2': '복사한 프롬프트를 채팅에 붙여넣습니다',
    'resume.guide3': 'AI가 체크포인트를 읽고 작업을 이어갑니다',
    'resume.closeGuide': '가이드 닫기',
    'resume.hookSetup': '처음이신가요? 자동 이어하기 훅 설정',
    'resume.hookDesc': '한 번 연결하면 AI 도구를 시작할 때마다 자동으로 이어하기가 활성화됩니다.',

    // Timeline detail
    'timeline.files': '파일',
    'timeline.commands': '명령어',
    'timeline.saveFailed': '저장 실패',

    // Common extras
    'common.switchLang': '언어 전환',
    'app.loading': 'HITS...',
  },
};

// --- Reactive locale store (Svelte-compatible) ---

type Listener = () => void;

class LocaleStore {
  private _value: Locale = 'en';
  private _listeners: Set<Listener> = new Set();

  constructor() {
    this._value = this._detect();
  }

  private _detect(): Locale {
    if (typeof window === 'undefined') return 'en';
    const saved = localStorage.getItem('hits-locale');
    if (saved === 'en' || saved === 'ko') return saved;
    const nav = navigator.language || '';
    return nav.startsWith('ko') ? 'ko' : 'en';
  }

  get value(): Locale {
    return this._value;
  }

  set value(newValue: Locale) {
    if (this._value === newValue) return;
    this._value = newValue;
    if (typeof window !== 'undefined') {
      localStorage.setItem('hits-locale', newValue);
    }
    this._listeners.forEach(fn => fn());
  }

  subscribe(fn: Listener): () => void {
    this._listeners.add(fn);
    return () => this._listeners.delete(fn);
  }
}

const localeStore = new LocaleStore();

/** Initialize locale from browser/storage. Call once in App.svelte onMount. */
export function initLocale(): Locale {
  return localeStore.value;
}

/** Get current locale. */
export function getLocale(): Locale {
  return localeStore.value;
}

/** Set locale and persist to localStorage. Triggers all reactive subscribers. */
export function setLocale(l: Locale): void {
  localeStore.value = l;
}

/** Subscribe to locale changes (Svelte $-syntax compatible). */
export function subscribeLocale(fn: Listener): () => void {
  return localeStore.subscribe(fn);
}

/** Translate a key. Reads current locale reactively. */
export function t(key: string): string {
  return translations[localeStore.value]?.[key] || translations['en']?.[key] || key;
}

/** Alternative language label for toggle button. */
export function altLang(): Locale {
  return localeStore.value === 'ko' ? 'en' : 'ko';
}

export function altLangLabel(): string {
  return localeStore.value === 'ko' ? 'EN' : '한';
}
