/** Shared, non-secret constants used by both contracts consumers. */

export const API_VERSION = 'v1';
export const API_PREFIX = `/api/${API_VERSION}`;

/** Canonical relative route builders (append to NEXT_PUBLIC_API_URL). */
export const API_ROUTES = {
  auth: {
    register: '/auth/register',
    login: '/auth/login',
    refresh: '/auth/refresh',
    logout: '/auth/logout',
    me: '/auth/me',
  },
  recruitment: {
    analyze: '/recruitment/analyze',
    uploadCvs: '/recruitment/upload-cvs',
    sessions: '/recruitment/sessions',
    session: (sessionId: string) => `/recruitment/sessions/${sessionId}`,
    fairness: (sessionId: string) => `/recruitment/fairness/${sessionId}`,
  },
  pricing: {
    optimize: '/pricing/optimize',
    history: '/pricing/history',
    analysis: (analysisId: string) => `/pricing/analyses/${analysisId}`,
  },
  forecasting: {
    forecast: '/forecasting/forecast',
    history: '/forecasting/history',
    detail: (forecastId: string) => `/forecasting/forecasts/${forecastId}`,
  },
  sustainability: {
    score: '/sustainability/score',
    assessments: '/sustainability/assessments',
    assessment: (assessmentId: string) => `/sustainability/assessments/${assessmentId}`,
  },
  chatbot: {
    message: '/chatbot/message',
    conversations: '/chatbot/conversations',
    messageDetail: (messageId: string) => `/chatbot/messages/${messageId}`,
    executiveReport: (reportId: string) => `/chatbot/executive-reports/${reportId}`,
  },
  context: { signals: '/context/signals', models: '/context/models' },
  audits: {
    list: '/audits',
    summary: '/audits/summary',
    fairness: '/audits/fairness',
    detail: (auditId: string) => `/audits/${auditId}`,
  },
} as const;

export const WS_ROUTES = {
  chatbot: (conversationId: string) => `/chatbot/ws/${conversationId}`,
} as const;
