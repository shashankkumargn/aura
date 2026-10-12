import React, { useState, useEffect, useRef } from 'react';
import {
  Sparkles,
  Send,
  MessageSquare,
  LayoutDashboard,
  Cpu,
  BookOpen,
  Code,
  Sliders,
  Bell,
  ChevronDown,
  Globe,
  Smartphone,
  MessageCircle,
  Monitor,
  CheckCircle2,
  Clock,
  Layers,
  ArrowRight,
  ThumbsUp,
  ThumbsDown,
  RefreshCw,
  Plus,
  PanelLeftClose,
  PanelLeftOpen,
  HelpCircle,
  Search,
  ExternalLink,
  ShieldCheck,
  Terminal,
  Activity,
  ShoppingBag,
  Gift,
  Package,
  CreditCard,
  Truck,
  RotateCcw,
  Wand2,
  X
} from 'lucide-react';

const TAB_LABELS = {
  overview: 'Overview',
  agent_playground: 'Agent playground',
  sessions: 'Sessions',
  agents: 'Agents',
  knowledge_base: 'Knowledge base',
  documentation: 'Documentation',
  settings: 'Settings',
};

const API_BASE = 'http://localhost:8000';

const TEAM_AGENTS = [
  { id: 'coordinator', name: 'Coordinator', desc: 'Classifies intent and routes incoming requests', Icon: Terminal },
  { id: 'supervisor', name: 'Supervisor', desc: 'Delegates tasks and applies policy checks', Icon: Layers },
  { id: 'planner', name: 'Planner', desc: 'Decomposes multi-part shopping requests', Icon: Search },
  { id: 'sales', name: 'Sales', desc: 'Product discovery and shopping assistance', Icon: ShoppingBag },
  { id: 'recommendation', name: 'Recommendation', desc: 'Personalized product recommendations', Icon: Gift },
  { id: 'inventory', name: 'Inventory', desc: 'Stock availability across channels', Icon: Package },
  { id: 'payment', name: 'Payment', desc: 'Mocked payment processing for the Phase-1 prototype', Icon: CreditCard },
  { id: 'fulfillment', name: 'Fulfillment', desc: 'Mocked order and shipment tracking for the Phase-1 prototype', Icon: Truck },
  { id: 'loyalty', name: 'Loyalty', desc: 'Rewards balance and redemption', Icon: Gift },
  { id: 'post_purchase', name: 'Post-Purchase', desc: 'Returns and after-sales support', Icon: RotateCcw },
  { id: 'output_composer', name: 'Output composer', desc: 'Combines agent outputs into one clear answer', Icon: Wand2 },
];

const CHANNELS = [
  { id: 'mobile', label: 'Mobile', icon: Smartphone, channelTag: 'mobile' },
  { id: 'web', label: 'Web Store', icon: Globe, channelTag: 'web' },
  { id: 'whatsapp_sim', label: 'WhatsApp', icon: MessageCircle, channelTag: 'whatsapp_sim' },
  { id: 'kiosk_sim', label: 'In-Store Kiosk', icon: Monitor, channelTag: 'kiosk_sim' },
];

const WELCOME_MESSAGE = {
  id: 'welcome',
  role: 'assistant',
  agent: 'AURA',
  content: "Hi, I'm AURA. Ask about products, stock, orders, loyalty, or returns — I'll route your request through the live agent pipeline.",
  source: null,
  latency: null,
};

function formatAgentLabel(agentId) {
  if (!agentId) return 'Coordinator';
  return String(agentId)
    .split('_')
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

function createSessionId() {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return `SES-${crypto.randomUUID().slice(0, 8).toUpperCase()}`;
  }
  return `SES-${Date.now().toString(36).toUpperCase()}`;
}

export default function App() {
  const [activeTab, setActiveTab] = useState('agent_playground');
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [inspectedAgent, setInspectedAgent] = useState(null);
  const [channel, setChannel] = useState(CHANNELS[0]); // default Mobile
  const [sessionId, setSessionId] = useState(() => createSessionId());
  const [messages, setMessages] = useState([WELCOME_MESSAGE]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [activeAgent, setActiveAgent] = useState('Coordinator');
  const [executionState, setExecutionState] = useState({
    coordinator: 'Ready',
    supervisor: 'Ready',
    subagent: 'Ready',
    composer: 'Ready',
    currentSubagentName: 'Sales',
  });
  const [lastRefreshed, setLastRefreshed] = useState('—');
  const [feedbackState, setFeedbackState] = useState({});
  const [backendOnline, setBackendOnline] = useState(false);
  const [statsLoading, setStatsLoading] = useState(false);
  const [statsError, setStatsError] = useState(null);
  const [agentStatsMap, setAgentStatsMap] = useState({});
  const [recentActivity, setRecentActivity] = useState([]);
  const [totalTurns, setTotalTurns] = useState(0);
  const [sessions, setSessions] = useState([]);
  const [overview, setOverview] = useState(null);
  const [knowledge, setKnowledge] = useState(null);

  const messagesEndRef = useRef(null);
  const mainRef = useRef(null);

  const refreshLiveData = async () => {
    setStatsLoading(true);
    setStatsError(null);
    try {
      const healthRes = await fetch(`${API_BASE}/health`);
      setBackendOnline(healthRes.ok);

      const [statsRes, sessionsRes, overviewRes, knowledgeRes] = await Promise.all([
        fetch(`${API_BASE}/admin/agent-stats?limit=500`),
        fetch(`${API_BASE}/admin/sessions?limit=200`),
        fetch(`${API_BASE}/admin/overview?limit=200`),
        fetch(`${API_BASE}/admin/knowledge`),
      ]);

      if (!statsRes.ok || !sessionsRes.ok || !overviewRes.ok || !knowledgeRes.ok) {
        throw new Error('One or more live data endpoints failed');
      }

      const [statsData, sessionsData, overviewData, knowledgeData] = await Promise.all([
        statsRes.json(),
        sessionsRes.json(),
        overviewRes.json(),
        knowledgeRes.json(),
      ]);

      const nextMap = {};
      (statsData.agents || []).forEach((row) => {
        nextMap[row.id] = {
          calls: row.calls || 0,
          avgMs: Math.round(row.avg_ms || 0),
        };
      });

      setAgentStatsMap(nextMap);
      setRecentActivity(Array.isArray(statsData.recent_activity) ? statsData.recent_activity : []);
      setTotalTurns(statsData.total_turns || 0);
      setSessions(Array.isArray(sessionsData) ? sessionsData : []);
      setOverview(overviewData);
      setKnowledge(knowledgeData);
      setLastRefreshed(new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }));
    } catch (err) {
      setBackendOnline(false);
      setStatsError(err.message || 'Failed to load live data');
    } finally {
      setStatsLoading(false);
    }
  };

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  useEffect(() => {
    setInspectedAgent(null);
    if (mainRef.current) {
      mainRef.current.scrollTop = 0;
    }
  }, [activeTab]);

  useEffect(() => {
    refreshLiveData();
    const interval = setInterval(refreshLiveData, 15000);
    return () => clearInterval(interval);
  }, []);

  const teamAgentsLive = TEAM_AGENTS.map((agent) => {
    const live = agentStatsMap[agent.id] || { calls: 0, avgMs: 0 };
    return {
      ...agent,
      calls: live.calls,
      avgMs: live.avgMs,
      status: backendOnline ? 'Ready' : 'Offline',
    };
  });

  const handleNewConversation = () => {
    setSessionId(createSessionId());
    setMessages([{ ...WELCOME_MESSAGE, id: `welcome-${Date.now()}` }]);
    setActiveAgent('Coordinator');
    setFeedbackState({});
    setExecutionState({
      coordinator: 'Ready',
      supervisor: 'Ready',
      subagent: 'Ready',
      composer: 'Ready',
      currentSubagentName: 'Coordinator',
    });
  };

  const handleSend = async (customText) => {
    const text = (customText || input).trim();
    if (!text || loading) return;

    const userMessageId = Date.now().toString();
    const userMessage = {
      id: userMessageId,
      role: 'user',
      content: text,
      source: null,
      latency: null,
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setLoading(true);

    const startTime = performance.now();

    // Visual step sequence
    setExecutionState({
      coordinator: 'Classifying intent...',
      supervisor: 'Pending',
      subagent: 'Pending',
      composer: 'Pending',
      currentSubagentName: 'Coordinator',
    });

    try {
      const res = await fetch(`${API_BASE}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          channel: channel.channelTag,
          user_id: 'u123',
          message: text,
        }),
      });

      const elapsedSec = ((performance.now() - startTime) / 1000).toFixed(2);

      if (!res.ok) {
        throw new Error(`Server returned status ${res.status}`);
      }

      const data = await res.json();
      const domainAgents = (data.agents_used || []).filter(
        (id) => !['coordinator', 'supervisor', 'planner', 'output_composer'].includes(String(id).toLowerCase())
      );
      const primaryAgentId = domainAgents[0] || (data.agents_used && data.agents_used[0]) || 'coordinator';
      const primaryAgent = formatAgentLabel(primaryAgentId);

      setActiveAgent(primaryAgent);

      setExecutionState({
        coordinator: 'Classified: ' + (data.intent || 'unclassified'),
        supervisor: 'Dispatched: ' + ((data.agents_used && data.agents_used.length) ? data.agents_used.join(', ') : 'none'),
        subagent: 'Completed',
        composer: 'Synthesized for ' + channel.label,
        currentSubagentName: primaryAgent,
      });

      const assistantMessage = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        agent: primaryAgent,
        content: data.response || "I've processed your request.",
        source: (data.retrieved_sources && data.retrieved_sources.length > 0)
          ? data.retrieved_sources[0]
          : null,
        latency: `${elapsedSec} s`,
      };

      setMessages((prev) => [...prev, assistantMessage]);
      refreshLiveData();
    } catch (err) {
      const elapsedSec = ((performance.now() - startTime) / 1000).toFixed(2);
      setMessages((prev) => [
        ...prev,
        {
          id: (Date.now() + 1).toString(),
          role: 'assistant',
          agent: 'Coordinator',
          content: "Sorry, I could not connect to the backend server. Make sure `uvicorn app.main:app` is running on port 8000.",
          source: null,
          latency: `${elapsedSec} s`,
        }
      ]);
      setExecutionState({
        coordinator: 'Error connecting to :8000',
        supervisor: 'Skipped',
        subagent: 'Skipped',
        composer: 'Skipped',
        currentSubagentName: 'Coordinator',
      });
      setBackendOnline(false);
    } finally {
      setLoading(false);
    }
  };

  const handleFeedback = async (msgId, rating) => {
    setFeedbackState((prev) => ({ ...prev, [msgId]: rating }));
    try {
      await fetch(`${API_BASE}/admin/feedback`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          rating: rating,
          comment: `Rated from Agent Playground UI (${rating})`,
        }),
      });
    } catch (e) {
      // ignore
    }
  };

  return (
    <div style={{ display: 'flex', height: '100vh', width: '100%', backgroundColor: '#090d14', color: '#f8fafc', overflow: 'hidden' }}>
      
      {/* ================= LEFT SIDEBAR ================= */}
      <aside style={{
        width: sidebarCollapsed ? '0px' : '240px',
        minWidth: sidebarCollapsed ? '0px' : '240px',
        backgroundColor: '#0a0e17',
        borderRight: sidebarCollapsed ? 'none' : '1px solid #161f30',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
        padding: sidebarCollapsed ? '0' : '16px 12px',
        overflow: 'hidden',
        transition: 'width 0.2s ease, min-width 0.2s ease, padding 0.2s ease',
        userSelect: 'none',
      }}>
        <div>
          {/* Logo Brand Header */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', padding: '8px 12px 24px 12px' }}>
            <div style={{
              width: '28px',
              height: '28px',
              borderRadius: '7px',
              backgroundColor: 'rgba(16, 185, 129, 0.15)',
              border: '1px solid #10b981',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}>
              <Sparkles size={16} color="#34d399" />
            </div>
            <span style={{ fontSize: '1.25rem', fontWeight: '800', letterSpacing: '0.04em', color: '#ffffff' }}>
              AURA
            </span>
            <span style={{
              fontSize: '0.65rem',
              fontWeight: '700',
              padding: '2px 6px',
              backgroundColor: 'rgba(16, 185, 129, 0.15)',
              color: '#34d399',
              borderRadius: '4px',
              border: '1px solid rgba(16, 185, 129, 0.3)',
              letterSpacing: '0.05em',
            }}>
              BETA
            </span>
          </div>

          {/* Section: WORKSPACE */}
          <div style={{ fontSize: '0.68rem', fontWeight: '700', letterSpacing: '0.08em', color: '#475569', padding: '8px 12px 6px 12px' }}>
            WORKSPACE
          </div>
          <nav style={{ display: 'flex', flexDirection: 'column', gap: '3px' }}>
            <button
              onClick={() => setActiveTab('overview')}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '12px',
                padding: '9px 12px',
                borderRadius: '8px',
                border: 'none',
                backgroundColor: activeTab === 'overview' ? 'rgba(16, 185, 129, 0.12)' : 'transparent',
                color: activeTab === 'overview' ? '#34d399' : '#94a3b8',
                fontSize: '0.86rem',
                fontWeight: activeTab === 'overview' ? '600' : '500',
                cursor: 'pointer',
                textAlign: 'left',
                width: '100%',
              }}
            >
              <LayoutDashboard size={17} color={activeTab === 'overview' ? '#34d399' : '#64748b'} />
              <span>Overview</span>
            </button>

            <button
              onClick={() => setActiveTab('agent_playground')}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '12px',
                padding: '9px 12px',
                borderRadius: '8px',
                border: activeTab === 'agent_playground' ? '1px solid rgba(16, 185, 129, 0.25)' : '1px solid transparent',
                backgroundColor: activeTab === 'agent_playground' ? 'rgba(16, 185, 129, 0.12)' : 'transparent',
                color: activeTab === 'agent_playground' ? '#34d399' : '#94a3b8',
                fontSize: '0.86rem',
                fontWeight: activeTab === 'agent_playground' ? '600' : '500',
                cursor: 'pointer',
                textAlign: 'left',
                width: '100%',
              }}
            >
              <Sparkles size={17} color={activeTab === 'agent_playground' ? '#34d399' : '#64748b'} />
              <span>Agent playground</span>
            </button>

            <button
              onClick={() => setActiveTab('sessions')}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '12px',
                padding: '9px 12px',
                borderRadius: '8px',
                border: 'none',
                backgroundColor: activeTab === 'sessions' ? 'rgba(16, 185, 129, 0.12)' : 'transparent',
                color: activeTab === 'sessions' ? '#34d399' : '#94a3b8',
                fontSize: '0.86rem',
                fontWeight: activeTab === 'sessions' ? '600' : '500',
                cursor: 'pointer',
                textAlign: 'left',
                width: '100%',
              }}
            >
              <MessageSquare size={17} color={activeTab === 'sessions' ? '#34d399' : '#64748b'} />
              <span>Sessions</span>
            </button>

            <button
              onClick={() => setActiveTab('agents')}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '9px 12px',
                borderRadius: '8px',
                border: 'none',
                backgroundColor: activeTab === 'agents' ? 'rgba(16, 185, 129, 0.12)' : 'transparent',
                color: activeTab === 'agents' ? '#34d399' : '#94a3b8',
                fontSize: '0.86rem',
                fontWeight: activeTab === 'agents' ? '600' : '500',
                cursor: 'pointer',
                textAlign: 'left',
                width: '100%',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <Cpu size={17} color={activeTab === 'agents' ? '#34d399' : '#64748b'} />
                <span>Agents</span>
              </div>
              <span style={{
                fontSize: '0.72rem',
                backgroundColor: '#162133',
                color: '#94a3b8',
                padding: '1px 6px',
                borderRadius: '10px',
                fontWeight: '600',
              }}>
                {TEAM_AGENTS.length}
              </span>
            </button>

            <button
              onClick={() => setActiveTab('knowledge_base')}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '12px',
                padding: '9px 12px',
                borderRadius: '8px',
                border: 'none',
                backgroundColor: activeTab === 'knowledge_base' ? 'rgba(16, 185, 129, 0.12)' : 'transparent',
                color: activeTab === 'knowledge_base' ? '#34d399' : '#94a3b8',
                fontSize: '0.86rem',
                fontWeight: activeTab === 'knowledge_base' ? '600' : '500',
                cursor: 'pointer',
                textAlign: 'left',
                width: '100%',
              }}
            >
              <BookOpen size={17} color={activeTab === 'knowledge_base' ? '#34d399' : '#64748b'} />
              <span>Knowledge base</span>
            </button>
          </nav>

          {/* Section: RESOURCES */}
          <div style={{ fontSize: '0.68rem', fontWeight: '700', letterSpacing: '0.08em', color: '#475569', padding: '20px 12px 6px 12px' }}>
            RESOURCES
          </div>
          <nav style={{ display: 'flex', flexDirection: 'column', gap: '3px' }}>
            <button
              onClick={() => setActiveTab('documentation')}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '12px',
                padding: '9px 12px',
                borderRadius: '8px',
                border: 'none',
                backgroundColor: activeTab === 'documentation' ? 'rgba(16, 185, 129, 0.12)' : 'transparent',
                color: activeTab === 'documentation' ? '#34d399' : '#94a3b8',
                fontSize: '0.86rem',
                fontWeight: '500',
                cursor: 'pointer',
                textAlign: 'left',
                width: '100%',
              }}
            >
              <Code size={17} color="#64748b" />
              <span>Documentation</span>
            </button>

            <button
              onClick={() => setActiveTab('settings')}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '12px',
                padding: '9px 12px',
                borderRadius: '8px',
                border: 'none',
                backgroundColor: activeTab === 'settings' ? 'rgba(16, 185, 129, 0.12)' : 'transparent',
                color: activeTab === 'settings' ? '#34d399' : '#94a3b8',
                fontSize: '0.86rem',
                fontWeight: '500',
                cursor: 'pointer',
                textAlign: 'left',
                width: '100%',
              }}
            >
              <Sliders size={17} color="#64748b" />
              <span>Settings</span>
            </button>
          </nav>
        </div>

        {/* Bottom Sidebar Cards */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          {/* Workspace Activity Pill */}
          <div style={{
            backgroundColor: '#0e1524',
            border: '1px solid #19253d',
            borderRadius: '10px',
            padding: '10px 12px',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '7px' }}>
                <span style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: backendOnline ? '#10b981' : '#ef4444' }} className="pulsing-dot" />
                <span style={{ fontSize: '0.78rem', fontWeight: '600', color: '#e2e8f0' }}>Live workspace</span>
              </div>
              <Activity size={14} color={backendOnline ? '#34d399' : '#94a3b8'} />
            </div>
            <div style={{ fontSize: '0.7rem', color: '#64748b', marginBottom: '8px' }}>
              {TEAM_AGENTS.length} agents · {totalTurns} logged turns
            </div>
            <div style={{ display: 'flex', gap: '3px', alignItems: 'flex-end', minHeight: '12px' }}>
              {(recentActivity.length ? recentActivity : Array(12).fill(0)).map((val, idx) => {
                const maxVal = Math.max(...(recentActivity.length ? recentActivity : [1]), 1);
                const height = val > 0 ? Math.max(3, Math.round((val / maxVal) * 12)) : 3;
                return (
                  <div
                    key={idx}
                    style={{
                      flex: 1,
                      height: `${height}px`,
                      borderRadius: '2px',
                      backgroundColor: val > 0 ? '#10b981' : '#1e293b',
                    }}
                  />
                );
              })}
            </div>
          </div>

          {/* User Profile */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '8px 10px',
            borderRadius: '10px',
            backgroundColor: '#0c121e',
            border: '1px solid #162033',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '9px' }}>
              <div style={{
                width: '30px',
                height: '30px',
                borderRadius: '50%',
                backgroundColor: 'rgba(16, 185, 129, 0.2)',
                color: '#34d399',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '0.78rem',
                fontWeight: '700',
              }}>
                SK
              </div>
              <div style={{ lineHeight: '1.2' }}>
                <div style={{ fontSize: '0.82rem', fontWeight: '600', color: '#f1f5f9' }}>Shashank Kumar</div>
                <div style={{ fontSize: '0.7rem', color: '#64748b' }}>Personal workspace</div>
              </div>
            </div>
            <ChevronDown size={14} color="#64748b" />
          </div>
        </div>
      </aside>

      {/* ================= RIGHT MAIN APPLICATION ================= */}
      <div style={{ flex: 1, minWidth: 0, minHeight: 0, display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
        
        {/* Top Navbar */}
        <header style={{
          height: '52px',
          borderBottom: '1px solid #161f30',
          backgroundColor: '#0a0e17',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 24px',
        }}>
          {/* Breadcrumbs */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', fontSize: '0.82rem', color: '#64748b' }}>
            <button
              type="button"
              aria-label={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
              onClick={() => setSidebarCollapsed((prev) => !prev)}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                width: '28px',
                height: '28px',
                borderRadius: '6px',
                border: '1px solid #1c273d',
                backgroundColor: '#101624',
                cursor: 'pointer',
                padding: 0,
              }}
            >
              {sidebarCollapsed ? (
                <PanelLeftOpen size={16} color="#94a3b8" />
              ) : (
                <PanelLeftClose size={16} color="#94a3b8" />
              )}
            </button>
            <span>Workspace</span>
            <span style={{ color: '#334155' }}>›</span>
            <span style={{ color: '#e2e8f0', fontWeight: '500' }}>{TAB_LABELS[activeTab] || 'Workspace'}</span>
          </div>

          {/* Top Right Controls */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '4px 10px',
              backgroundColor: 'rgba(16, 185, 129, 0.1)',
              border: '1px solid rgba(16, 185, 129, 0.3)',
              borderRadius: '9999px',
              fontSize: '0.74rem',
              color: '#34d399',
              fontWeight: '600',
            }}>
              <span style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: '#10b981' }} />
              {backendOnline ? 'Live backend' : 'Backend offline'}
            </div>

            <div style={{
              padding: '4px 9px',
              backgroundColor: '#111726',
              border: '1px solid #1e283d',
              borderRadius: '6px',
              fontSize: '0.74rem',
              color: '#94a3b8',
              fontWeight: '500',
            }}>
              Phase 01
            </div>

            <button style={{
              background: 'transparent',
              border: 'none',
              color: '#94a3b8',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              padding: '4px',
            }}>
              <Bell size={16} />
            </button>

            <div style={{
              width: '28px',
              height: '28px',
              borderRadius: '50%',
              backgroundColor: 'rgba(16, 185, 129, 0.2)',
              color: '#34d399',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '0.75rem',
              fontWeight: '700',
            }}>
              SK
            </div>
          </div>
        </header>

        {/* Content Body Container */}
        <main
          ref={mainRef}
          className="app-scroll"
          style={{ flex: 1, minHeight: 0, padding: '24px 28px', overflowY: 'auto', backgroundColor: '#090d14' }}
        >
          {activeTab === 'agents' && (
            <div>
              <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: '22px' }}>
                <div>
                  <h1 style={{ fontSize: '1.75rem', fontWeight: '800', color: '#ffffff', letterSpacing: '-0.02em', marginBottom: '4px' }}>
                    Your agent team
                  </h1>
                  <p style={{ fontSize: '0.88rem', color: '#64748b' }}>
                    Specialized intelligence, working together.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    refreshLiveData();
                    if (mainRef.current) mainRef.current.scrollTop = 0;
                  }}
                  disabled={statsLoading}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    padding: '9px 16px',
                    borderRadius: '8px',
                    backgroundColor: '#34d399',
                    color: '#064e3b',
                    fontWeight: '700',
                    fontSize: '0.85rem',
                    border: 'none',
                    cursor: statsLoading ? 'wait' : 'pointer',
                    opacity: statsLoading ? 0.75 : 1,
                    boxShadow: '0 4px 12px rgba(16, 185, 129, 0.25)',
                  }}
                >
                  <RefreshCw size={15} color="#064e3b" />
                  <span>{statsLoading ? 'Refreshing…' : 'Refresh data'}</span>
                </button>
              </div>

              {statsError && (
                <div style={{
                  marginBottom: '16px',
                  padding: '12px 14px',
                  borderRadius: '10px',
                  border: '1px solid rgba(239, 68, 68, 0.35)',
                  backgroundColor: 'rgba(239, 68, 68, 0.08)',
                  color: '#fca5a5',
                  fontSize: '0.82rem',
                }}>
                  Live agent stats unavailable: {statsError}
                </div>
              )}

              <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(3, minmax(0, 1fr))',
                gap: '16px',
                paddingBottom: '28px',
              }}>
                {teamAgentsLive.map((agent) => {
                  const Icon = agent.Icon;
                  const statusColor = agent.status === 'Ready' ? '#34d399' : '#f87171';
                  return (
                    <div
                      key={agent.id}
                      style={{
                        backgroundColor: '#0c111c',
                        border: inspectedAgent?.id === agent.id ? '1px solid rgba(16, 185, 129, 0.45)' : '1px solid #162033',
                        borderRadius: '14px',
                        padding: '18px 18px 14px',
                        display: 'flex',
                        flexDirection: 'column',
                        minHeight: '210px',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: '12px' }}>
                        <div style={{
                          width: '36px',
                          height: '36px',
                          borderRadius: '10px',
                          backgroundColor: 'rgba(16, 185, 129, 0.12)',
                          border: '1px solid rgba(16, 185, 129, 0.25)',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                        }}>
                          <Icon size={16} color="#34d399" />
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.72rem', color: statusColor, fontWeight: '600' }}>
                          <span style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: statusColor }} />
                          {agent.status}
                        </div>
                      </div>
                      <div style={{ fontSize: '0.98rem', fontWeight: '700', color: '#f8fafc', marginBottom: '4px' }}>{agent.name}</div>
                      <div style={{ fontSize: '0.8rem', color: '#64748b', lineHeight: 1.4, minHeight: '38px' }}>{agent.desc}</div>
                      <div style={{ display: 'flex', gap: '28px', marginTop: '18px', marginBottom: '14px' }}>
                        <div>
                          <div style={{ fontSize: '0.7rem', color: '#64748b', marginBottom: '4px' }}>Total calls</div>
                          <div style={{ fontSize: '1.15rem', fontWeight: '700', color: '#f1f5f9' }}>{agent.calls}</div>
                        </div>
                        <div>
                          <div style={{ fontSize: '0.7rem', color: '#64748b', marginBottom: '4px' }}>Avg. response</div>
                          <div style={{ fontSize: '1.15rem', fontWeight: '700', color: '#f1f5f9' }}>{agent.avgMs} ms</div>
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={() => setInspectedAgent(agent)}
                        style={{
                          marginTop: 'auto',
                          width: '100%',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          gap: '8px',
                          padding: '9px 12px',
                          borderRadius: '8px',
                          backgroundColor: '#101624',
                          border: '1px solid #1c273d',
                          color: '#cbd5e1',
                          fontSize: '0.82rem',
                          fontWeight: '600',
                          cursor: 'pointer',
                        }}
                      >
                        Inspect agent
                        <ExternalLink size={13} color="#94a3b8" />
                      </button>
                    </div>
                  );
                })}
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#64748b', fontSize: '0.75rem', paddingBottom: '8px' }}>
                <span style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: backendOnline ? '#10b981' : '#ef4444' }} />
                Live agent_logs · last refreshed {lastRefreshed}
              </div>
            </div>
          )}

          {activeTab === 'overview' && (
            <div>
              <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: '22px' }}>
                <div>
                  <h1 style={{ fontSize: '1.75rem', fontWeight: '800', color: '#ffffff', letterSpacing: '-0.02em', marginBottom: '4px' }}>Overview</h1>
                  <p style={{ fontSize: '0.88rem', color: '#64748b' }}>Live latency, channel mix, and routing from agent_logs.</p>
                </div>
                <button type="button" onClick={refreshLiveData} style={{ padding: '9px 16px', borderRadius: '8px', backgroundColor: '#34d399', color: '#064e3b', fontWeight: '700', fontSize: '0.85rem', border: 'none', cursor: 'pointer' }}>
                  Refresh data
                </button>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, minmax(0, 1fr))', gap: '14px', marginBottom: '18px' }}>
                {[
                  { label: 'Logged turns', value: overview?.latency?.count ?? totalTurns },
                  { label: 'Mean latency', value: `${Math.round(overview?.latency?.mean_ms || 0)} ms` },
                  { label: 'P95 latency', value: `${Math.round(overview?.latency?.p95_ms || 0)} ms` },
                  { label: 'Sessions', value: sessions.length },
                ].map((card) => (
                  <div key={card.label} style={{ backgroundColor: '#0c111c', border: '1px solid #162033', borderRadius: '12px', padding: '16px' }}>
                    <div style={{ fontSize: '0.72rem', color: '#64748b', marginBottom: '6px' }}>{card.label}</div>
                    <div style={{ fontSize: '1.25rem', fontWeight: '700', color: '#f8fafc' }}>{card.value}</div>
                  </div>
                ))}
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px' }}>
                <div style={{ backgroundColor: '#0c111c', border: '1px solid #162033', borderRadius: '12px', padding: '16px' }}>
                  <div style={{ fontSize: '0.9rem', fontWeight: '700', marginBottom: '12px' }}>Channels</div>
                  {Object.keys(overview?.channels || {}).length === 0 && <div style={{ color: '#64748b', fontSize: '0.82rem' }}>No channel activity yet.</div>}
                  {Object.entries(overview?.channels || {}).map(([name, count]) => (
                    <div key={name} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.82rem', color: '#cbd5e1', marginBottom: '8px' }}>
                      <span>{name}</span><span>{count}</span>
                    </div>
                  ))}
                </div>
                <div style={{ backgroundColor: '#0c111c', border: '1px solid #162033', borderRadius: '12px', padding: '16px' }}>
                  <div style={{ fontSize: '0.9rem', fontWeight: '700', marginBottom: '12px' }}>Intents</div>
                  {Object.keys(overview?.intents || {}).length === 0 && <div style={{ color: '#64748b', fontSize: '0.82rem' }}>No intents logged yet.</div>}
                  {Object.entries(overview?.intents || {}).map(([name, count]) => (
                    <div key={name} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.82rem', color: '#cbd5e1', marginBottom: '8px' }}>
                      <span>{name}</span><span>{count}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {activeTab === 'sessions' && (
            <div>
              <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: '22px' }}>
                <div>
                  <h1 style={{ fontSize: '1.75rem', fontWeight: '800', color: '#ffffff', letterSpacing: '-0.02em', marginBottom: '4px' }}>Sessions</h1>
                  <p style={{ fontSize: '0.88rem', color: '#64748b' }}>Conversation sessions persisted in agent_logs.</p>
                </div>
                <button type="button" onClick={refreshLiveData} style={{ padding: '9px 16px', borderRadius: '8px', backgroundColor: '#34d399', color: '#064e3b', fontWeight: '700', fontSize: '0.85rem', border: 'none', cursor: 'pointer' }}>
                  Refresh data
                </button>
              </div>
              {sessions.length === 0 ? (
                <div style={{ backgroundColor: '#0c111c', border: '1px solid #162033', borderRadius: '14px', padding: '22px', color: '#94a3b8' }}>
                  No sessions logged yet. Chat in Agent playground to create live session history.
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', paddingBottom: '24px' }}>
                  {sessions.map((session) => (
                    <div key={session.session_id} style={{ backgroundColor: '#0c111c', border: '1px solid #162033', borderRadius: '12px', padding: '16px' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', marginBottom: '8px' }}>
                        <div style={{ fontWeight: '700', color: '#f8fafc' }}>{session.session_id}</div>
                        <div style={{ fontSize: '0.75rem', color: '#64748b' }}>{session.last_timestamp || '—'}</div>
                      </div>
                      <div style={{ fontSize: '0.8rem', color: '#94a3b8', marginBottom: '8px' }}>
                        {session.channel || 'unknown'} · {session.turn_count} turns · {session.last_intent || 'unclassified'}
                      </div>
                      <div style={{ fontSize: '0.84rem', color: '#cbd5e1', lineHeight: 1.45 }}>
                        {session.last_user_message || 'No user message'}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {activeTab === 'knowledge_base' && (
            <div>
              <h1 style={{ fontSize: '1.75rem', fontWeight: '800', color: '#ffffff', letterSpacing: '-0.02em', marginBottom: '4px' }}>Knowledge base</h1>
              <p style={{ fontSize: '0.88rem', color: '#64748b', marginBottom: '20px' }}>
                Catalog and policy documents currently loaded in SQLite.
              </p>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px', marginBottom: '16px' }}>
                <div style={{ backgroundColor: '#0c111c', border: '1px solid #162033', borderRadius: '12px', padding: '16px' }}>
                  <div style={{ fontSize: '0.72rem', color: '#64748b' }}>Products</div>
                  <div style={{ fontSize: '1.3rem', fontWeight: '700' }}>{knowledge?.product_count ?? 0}</div>
                </div>
                <div style={{ backgroundColor: '#0c111c', border: '1px solid #162033', borderRadius: '12px', padding: '16px' }}>
                  <div style={{ fontSize: '0.72rem', color: '#64748b' }}>Policies</div>
                  <div style={{ fontSize: '1.3rem', fontWeight: '700' }}>{knowledge?.policy_count ?? 0}</div>
                </div>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px' }}>
                <div style={{ backgroundColor: '#0c111c', border: '1px solid #162033', borderRadius: '12px', padding: '16px' }}>
                  <div style={{ fontWeight: '700', marginBottom: '10px' }}>Policies</div>
                  {(knowledge?.policies || []).slice(0, 8).map((doc) => (
                    <div key={doc.id} style={{ marginBottom: '10px' }}>
                      <div style={{ fontSize: '0.84rem', color: '#e2e8f0', fontWeight: '600' }}>{doc.title}</div>
                      <div style={{ fontSize: '0.75rem', color: '#64748b' }}>{doc.category}</div>
                    </div>
                  ))}
                  {!knowledge?.policies?.length && <div style={{ color: '#64748b', fontSize: '0.82rem' }}>No policies in database.</div>}
                </div>
                <div style={{ backgroundColor: '#0c111c', border: '1px solid #162033', borderRadius: '12px', padding: '16px' }}>
                  <div style={{ fontWeight: '700', marginBottom: '10px' }}>Sample products</div>
                  {(knowledge?.products || []).slice(0, 8).map((product) => (
                    <div key={product.id} style={{ marginBottom: '10px' }}>
                      <div style={{ fontSize: '0.84rem', color: '#e2e8f0', fontWeight: '600' }}>{product.name}</div>
                      <div style={{ fontSize: '0.75rem', color: '#64748b' }}>{product.brand} · ₹{product.price} · stock {product.stock_qty}</div>
                    </div>
                  ))}
                  {!knowledge?.products?.length && <div style={{ color: '#64748b', fontSize: '0.82rem' }}>No products in database.</div>}
                </div>
              </div>
            </div>
          )}

          {(activeTab === 'documentation' || activeTab === 'settings') && (
            <div>
              <h1 style={{ fontSize: '1.75rem', fontWeight: '800', color: '#ffffff', letterSpacing: '-0.02em', marginBottom: '8px' }}>
                {TAB_LABELS[activeTab]}
              </h1>
              <div style={{
                backgroundColor: '#0c111c',
                border: '1px solid #162033',
                borderRadius: '14px',
                padding: '22px',
                color: '#94a3b8',
                fontSize: '0.88rem',
                lineHeight: 1.5,
              }}>
                {activeTab === 'documentation' && 'AURA architecture: Coordinator → Supervisor → (Planner or domain agent) → Output Composer. Domain agents call only their allow-listed tools.'}
                {activeTab === 'settings' && `Backend ${backendOnline ? 'online' : 'offline'} at ${API_BASE}. LLM provider is read from backend/.env. Metrics refresh every 15s from /admin/* endpoints.`}
              </div>
            </div>
          )}

          {activeTab === 'agent_playground' && (
          <>
          {/* Main Title Row */}
          <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: '20px' }}>
            <div>
              <h1 style={{ fontSize: '1.75rem', fontWeight: '800', color: '#ffffff', letterSpacing: '-0.02em', marginBottom: '4px' }}>
                Agent playground
              </h1>
              <p style={{ fontSize: '0.88rem', color: '#64748b' }}>
                Your retail assistant, across every conversation.
              </p>
            </div>

            <button
              onClick={handleNewConversation}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '9px 16px',
                borderRadius: '8px',
                backgroundColor: '#34d399',
                color: '#064e3b',
                fontWeight: '700',
                fontSize: '0.85rem',
                border: 'none',
                cursor: 'pointer',
                boxShadow: '0 4px 12px rgba(16, 185, 129, 0.25)',
                transition: 'all 0.15s ease',
              }}
            >
              <MessageSquare size={15} color="#064e3b" />
              <span>New conversation</span>
            </button>
          </div>

          {/* Playground Grid (Left: Chat Window | Right: Context & Execution Path) */}
          <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) 310px', gap: '20px' }}>
            
            {/* ================= CENTER CHAT CARD ================= */}
            <div style={{
              backgroundColor: '#0c111c',
              border: '1px solid #162033',
              borderRadius: '16px',
              display: 'flex',
              flexDirection: 'column',
              minHeight: '640px',
              height: 'calc(100vh - 180px)',
              boxShadow: '0 12px 30px rgba(0, 0, 0, 0.35)',
            }}>
              
              {/* Chat Card Header */}
              <div style={{
                padding: '14px 20px',
                borderBottom: '1px solid #162033',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <div style={{
                    width: '32px',
                    height: '32px',
                    borderRadius: '8px',
                    backgroundColor: 'rgba(16, 185, 129, 0.15)',
                    border: '1px solid rgba(16, 185, 129, 0.3)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}>
                    <Sparkles size={17} color="#34d399" />
                  </div>
                  <div>
                    <div style={{ fontSize: '0.92rem', fontWeight: '700', color: '#f1f5f9' }}>AURA assistant</div>
                    <div style={{ fontSize: '0.72rem', color: '#64748b' }}>Session · {sessionId}</div>
                  </div>
                </div>

                {/* Simulated Channel Dropdown */}
                <div style={{ position: 'relative' }}>
                  <select
                    value={channel.id}
                    onChange={(e) => {
                      const sel = CHANNELS.find((c) => c.id === e.target.value);
                      if (sel) setChannel(sel);
                    }}
                    style={{
                      appearance: 'none',
                      backgroundColor: '#111726',
                      border: '1px solid #1c273d',
                      borderRadius: '8px',
                      padding: '7px 32px 7px 12px',
                      color: '#e2e8f0',
                      fontSize: '0.8rem',
                      fontWeight: '600',
                      cursor: 'pointer',
                      outline: 'none',
                    }}
                  >
                    {CHANNELS.map((ch) => (
                      <option key={ch.id} value={ch.id}>
                        {ch.label}
                      </option>
                    ))}
                  </select>
                  <ChevronDown
                    size={14}
                    color="#94a3b8"
                    style={{ position: 'absolute', right: '10px', top: '50%', transform: 'translateY(-50%)', pointerEvents: 'none' }}
                  />
                </div>
              </div>

              {/* Message History Area */}
              <div style={{
                flex: 1,
                padding: '24px 20px',
                overflowY: 'auto',
                display: 'flex',
                flexDirection: 'column',
                gap: '20px',
              }}>
                {messages.map((m) => {
                  if (m.role === 'user') {
                    return (
                      <div key={m.id} style={{ display: 'flex', justifyContent: 'flex-end' }}>
                        <div style={{
                          backgroundColor: '#182133',
                          border: '1px solid #23314a',
                          color: '#f8fafc',
                          padding: '10px 16px',
                          borderRadius: '14px 14px 2px 14px',
                          maxWidth: '75%',
                          fontSize: '0.9rem',
                          lineHeight: '1.45',
                        }}>
                          {m.content}
                        </div>
                      </div>
                    );
                  }

                  // Assistant Message
                  return (
                    <div key={m.id} style={{ display: 'flex', flexDirection: 'column', gap: '6px', maxWidth: '85%' }}>
                      {/* Message Sender Header */}
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <Sparkles size={14} color="#34d399" />
                        <span style={{ fontSize: '0.82rem', fontWeight: '700', color: '#ffffff' }}>AURA</span>
                        <span style={{
                          fontSize: '0.68rem',
                          fontWeight: '700',
                          backgroundColor: 'rgba(16, 185, 129, 0.15)',
                          color: '#34d399',
                          border: '1px solid rgba(16, 185, 129, 0.3)',
                          padding: '1px 7px',
                          borderRadius: '4px',
                          letterSpacing: '0.03em',
                        }}>
                          {m.agent || 'Sales'}
                        </span>
                      </div>

                      {/* Content Body */}
                      <div style={{
                        color: '#e2e8f0',
                        fontSize: '0.9rem',
                        lineHeight: '1.55',
                        whiteSpace: 'pre-line',
                      }}>
                        {m.content}
                      </div>

                      {/* Message Footer (Source & Latency) */}
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: '4px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                          {m.source && (
                            <div style={{ display: 'flex', alignItems: 'center', gap: '5px', fontSize: '0.74rem', color: '#64748b' }}>
                              <BookOpen size={12} color="#64748b" />
                              <span>Source: {m.source}</span>
                            </div>
                          )}
                          {/* Feedback Thumbs */}
                          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                            <button
                              onClick={() => handleFeedback(m.id, 'up')}
                              style={{
                                background: 'transparent',
                                border: 'none',
                                cursor: 'pointer',
                                color: feedbackState[m.id] === 'up' ? '#10b981' : '#475569',
                                padding: '2px',
                              }}
                            >
                              <ThumbsUp size={12} />
                            </button>
                            <button
                              onClick={() => handleFeedback(m.id, 'down')}
                              style={{
                                background: 'transparent',
                                border: 'none',
                                cursor: 'pointer',
                                color: feedbackState[m.id] === 'down' ? '#ef4444' : '#475569',
                                padding: '2px',
                              }}
                            >
                              <ThumbsDown size={12} />
                            </button>
                          </div>
                        </div>

                        {m.latency && (
                          <div style={{ fontSize: '0.74rem', color: '#64748b', fontFamily: 'monospace' }}>
                            {m.latency}
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}

                {/* Loading state indicator */}
                {loading && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <Sparkles size={14} color="#34d399" />
                      <span style={{ fontSize: '0.82rem', fontWeight: '700', color: '#ffffff' }}>AURA</span>
                      <span style={{ fontSize: '0.72rem', color: '#64748b' }}>orchestrating specialized agents...</span>
                    </div>
                    <div style={{ display: 'flex', gap: '5px', padding: '6px 0' }}>
                      <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#10b981' }} className="typing-dot-1" />
                      <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#10b981' }} className="typing-dot-2" />
                      <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#10b981' }} className="typing-dot-3" />
                    </div>
                  </div>
                )}

                <div ref={messagesEndRef} />
              </div>

              {/* Chat Input Container */}
              <div style={{
                padding: '16px 20px',
                borderTop: '1px solid #162033',
              }}>
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    handleSend();
                  }}
                  style={{
                    backgroundColor: '#111726',
                    border: '1px solid #1e2a42',
                    borderRadius: '12px',
                    display: 'flex',
                    alignItems: 'center',
                    padding: '6px 8px 6px 16px',
                  }}
                >
                  <input
                    type="text"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    placeholder="Ask AURA anything about your shopping..."
                    style={{
                      flex: 1,
                      background: 'transparent',
                      border: 'none',
                      outline: 'none',
                      color: '#f8fafc',
                      fontSize: '0.88rem',
                    }}
                  />
                  <button
                    type="submit"
                    disabled={loading || !input.trim()}
                    style={{
                      width: '36px',
                      height: '36px',
                      borderRadius: '8px',
                      backgroundColor: input.trim() ? '#34d399' : '#1e293b',
                      border: 'none',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      cursor: input.trim() ? 'pointer' : 'default',
                      transition: 'background-color 0.15s ease',
                    }}
                  >
                    <Send size={16} color={input.trim() ? '#064e3b' : '#64748b'} />
                  </button>
                </form>

                {/* Quick Suggestion Pills */}
                <div style={{ display: 'flex', gap: '8px', marginTop: '10px', overflowX: 'auto' }}>
                  {[
                    "Show wireless earphones under 2000",
                    "Is boAt neckband P001 in stock?",
                    "Where is my order ORD-1001?",
                    "Recommend running shoes",
                  ].map((chip, idx) => (
                    <button
                      key={idx}
                      onClick={() => handleSend(chip)}
                      style={{
                        padding: '4px 10px',
                        backgroundColor: '#0f172a',
                        border: '1px solid #1e293b',
                        borderRadius: '6px',
                        color: '#94a3b8',
                        fontSize: '0.74rem',
                        cursor: 'pointer',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {chip}
                    </button>
                  ))}
                </div>
              </div>

              {/* Bottom Card Footer Status */}
              <div style={{
                padding: '8px 20px',
                borderTop: '1px solid #141c2c',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                fontSize: '0.72rem',
                color: '#64748b',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <span style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: '#10b981' }} />
                  Live data · last refreshed {lastRefreshed}
                </div>
                <div>
                  AURA v1.0 · Agentic Unified Retail Assistant
                </div>
              </div>

            </div>

            {/* ================= RIGHT CONTEXT & EXECUTION PANELS ================= */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              
              {/* Card 1: Conversation Context */}
              <div style={{
                backgroundColor: '#0c111c',
                border: '1px solid #162033',
                borderRadius: '14px',
                padding: '18px',
              }}>
                <h3 style={{ fontSize: '0.92rem', fontWeight: '700', color: '#f8fafc', marginBottom: '2px' }}>
                  Conversation context
                </h3>
                <p style={{ fontSize: '0.74rem', color: '#64748b', marginBottom: '16px' }}>
                  Shared across channels
                </p>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px', marginBottom: '14px' }}>
                  <div>
                    <div style={{ fontSize: '0.68rem', fontWeight: '700', letterSpacing: '0.05em', color: '#64748b', marginBottom: '2px' }}>
                      SESSION
                    </div>
                    <div style={{ fontSize: '0.85rem', fontWeight: '700', color: '#e2e8f0', fontFamily: 'monospace' }}>
                      {sessionId}
                    </div>
                  </div>

                  <div>
                    <div style={{ fontSize: '0.68rem', fontWeight: '700', letterSpacing: '0.05em', color: '#64748b', marginBottom: '2px' }}>
                      CHANNEL
                    </div>
                    <div style={{ fontSize: '0.85rem', fontWeight: '700', color: '#e2e8f0' }}>
                      {channel.label}
                    </div>
                  </div>

                  <div>
                    <div style={{ fontSize: '0.68rem', fontWeight: '700', letterSpacing: '0.05em', color: '#64748b', marginBottom: '2px' }}>
                      MESSAGES
                    </div>
                    <div style={{ fontSize: '0.85rem', fontWeight: '700', color: '#e2e8f0' }}>
                      {messages.length}
                    </div>
                  </div>

                  <div>
                    <div style={{ fontSize: '0.68rem', fontWeight: '700', letterSpacing: '0.05em', color: '#64748b', marginBottom: '2px' }}>
                      ACTIVE AGENT
                    </div>
                    <div style={{ fontSize: '0.85rem', fontWeight: '700', color: '#34d399' }}>
                      {activeAgent}
                    </div>
                  </div>
                </div>

                <div style={{
                  fontSize: '0.72rem',
                  color: '#64748b',
                  lineHeight: '1.4',
                  paddingTop: '10px',
                  borderTop: '1px solid #162033',
                }}>
                  Short-term conversation context remains available when you switch channels.
                </div>
              </div>

              {/* Card 2: Live Execution Path */}
              <div style={{
                backgroundColor: '#0c111c',
                border: '1px solid #162033',
                borderRadius: '14px',
                padding: '18px',
                flex: 1,
              }}>
                <h3 style={{ fontSize: '0.92rem', fontWeight: '700', color: '#f8fafc', marginBottom: '14px' }}>
                  Live execution path
                </h3>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                  
                  {/* Step 1: Coordinator */}
                  <div style={{
                    backgroundColor: '#101624',
                    border: '1px solid #182338',
                    borderRadius: '10px',
                    padding: '10px 12px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '12px',
                  }}>
                    <div style={{
                      width: '32px',
                      height: '32px',
                      borderRadius: '8px',
                      backgroundColor: 'rgba(16, 185, 129, 0.12)',
                      border: '1px solid rgba(16, 185, 129, 0.25)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}>
                      <Terminal size={15} color="#34d399" />
                    </div>
                    <div>
                      <div style={{ fontSize: '0.82rem', fontWeight: '700', color: '#f1f5f9' }}>Coordinator</div>
                      <div style={{ fontSize: '0.7rem', color: '#64748b' }}>{executionState.coordinator}</div>
                    </div>
                  </div>

                  {/* Step 2: Supervisor */}
                  <div style={{
                    backgroundColor: '#101624',
                    border: '1px solid #182338',
                    borderRadius: '10px',
                    padding: '10px 12px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '12px',
                  }}>
                    <div style={{
                      width: '32px',
                      height: '32px',
                      borderRadius: '8px',
                      backgroundColor: 'rgba(16, 185, 129, 0.12)',
                      border: '1px solid rgba(16, 185, 129, 0.25)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}>
                      <Layers size={15} color="#34d399" />
                    </div>
                    <div>
                      <div style={{ fontSize: '0.82rem', fontWeight: '700', color: '#f1f5f9' }}>Supervisor</div>
                      <div style={{ fontSize: '0.7rem', color: '#64748b' }}>{executionState.supervisor}</div>
                    </div>
                  </div>

                  {/* Step 3: Specialized Subagent */}
                  <div style={{
                    backgroundColor: '#101624',
                    border: '1px solid #182338',
                    borderRadius: '10px',
                    padding: '10px 12px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '12px',
                  }}>
                    <div style={{
                      width: '32px',
                      height: '32px',
                      borderRadius: '8px',
                      backgroundColor: 'rgba(16, 185, 129, 0.12)',
                      border: '1px solid rgba(16, 185, 129, 0.25)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}>
                      <Cpu size={15} color="#34d399" />
                    </div>
                    <div>
                      <div style={{ fontSize: '0.82rem', fontWeight: '700', color: '#f1f5f9' }}>{executionState.currentSubagentName || 'Domain Subagent'}</div>
                      <div style={{ fontSize: '0.7rem', color: '#64748b' }}>{executionState.subagent}</div>
                    </div>
                  </div>

                  {/* Step 4: Output Composer */}
                  <div style={{
                    backgroundColor: '#101624',
                    border: '1px solid #182338',
                    borderRadius: '10px',
                    padding: '10px 12px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '12px',
                  }}>
                    <div style={{
                      width: '32px',
                      height: '32px',
                      borderRadius: '8px',
                      backgroundColor: 'rgba(16, 185, 129, 0.12)',
                      border: '1px solid rgba(16, 185, 129, 0.25)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}>
                      <CheckCircle2 size={15} color="#34d399" />
                    </div>
                    <div>
                      <div style={{ fontSize: '0.82rem', fontWeight: '700', color: '#f1f5f9' }}>Output composer</div>
                      <div style={{ fontSize: '0.7rem', color: '#64748b' }}>{executionState.composer}</div>
                    </div>
                  </div>

                </div>
              </div>

            </div>

          </div>
          </>
          )}

        </main>

        {inspectedAgent && (
          <div
            onClick={() => setInspectedAgent(null)}
            style={{
              position: 'fixed',
              inset: 0,
              backgroundColor: 'rgba(0, 0, 0, 0.55)',
              zIndex: 40,
              display: 'flex',
              justifyContent: 'flex-end',
            }}
          >
            <aside
              onClick={(e) => e.stopPropagation()}
              style={{
                width: '380px',
                maxWidth: '100%',
                height: '100%',
                backgroundColor: '#0a0e17',
                borderLeft: '1px solid #162033',
                padding: '22px',
                overflowY: 'auto',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '18px' }}>
                <div style={{ fontSize: '0.78rem', color: '#64748b', fontWeight: '600' }}>Agent inspect</div>
                <button
                  type="button"
                  onClick={() => setInspectedAgent(null)}
                  style={{ background: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer' }}
                >
                  <X size={16} />
                </button>
              </div>
              <div style={{ fontSize: '1.2rem', fontWeight: '800', color: '#f8fafc', marginBottom: '6px' }}>{inspectedAgent.name}</div>
              <div style={{ fontSize: '0.86rem', color: '#94a3b8', lineHeight: 1.5, marginBottom: '18px' }}>{inspectedAgent.desc}</div>
              <div style={{ display: 'flex', gap: '16px', marginBottom: '20px' }}>
                <div>
                  <div style={{ fontSize: '0.7rem', color: '#64748b' }}>Total calls</div>
                  <div style={{ fontSize: '1.1rem', fontWeight: '700' }}>{inspectedAgent.calls}</div>
                </div>
                <div>
                  <div style={{ fontSize: '0.7rem', color: '#64748b' }}>Avg. response</div>
                  <div style={{ fontSize: '1.1rem', fontWeight: '700' }}>{inspectedAgent.avgMs} ms</div>
                </div>
              </div>
              <button
                type="button"
                onClick={() => {
                  setInspectedAgent(null);
                  setActiveTab('agent_playground');
                }}
                style={{
                  width: '100%',
                  padding: '10px 12px',
                  borderRadius: '8px',
                  backgroundColor: '#34d399',
                  color: '#064e3b',
                  fontWeight: '700',
                  fontSize: '0.85rem',
                  border: 'none',
                  cursor: 'pointer',
                }}
              >
                Open in playground
              </button>
            </aside>
          </div>
        )}

      </div>

    </div>
  );
}
