import {
  AlertCircle,
  ArrowLeft,
  ArrowRight,
  BadgeCheck,
  BookOpen,
  Check,
  ChevronRight,
  CircleDot,
  ClipboardList,
  Clock3,
  Database,
  FileQuestion,
  Filter,
  Fingerprint,
  FlaskConical,
  FolderOpen,
  Gavel,
  KeyRound,
  LoaderCircle,
  LockKeyhole,
  MapPin,
  Menu,
  Plus,
  Quote,
  RotateCcw,
  Search,
  Send,
  ShieldCheck,
  Sparkles,
  TriangleAlert,
  UserRoundSearch,
  UsersRound,
  X,
} from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { ApiError, gameApi } from './api'
import type {
  AccusationResult,
  AccusationReview,
  DialogueEntry,
  Evidence,
  EvidenceState,
  GameState,
  Notebook,
  Suspect,
  TheoryMap,
} from './types'

const STORAGE_KEY = 'ai-detective-current-case'
const EXAMPLE_QUESTIONS = [
  '案发时间前后你在哪里？',
  '谁能证明你的行踪？',
  '你最后一次见到死者是什么时候？',
  '你和死者最近发生过冲突吗？',
]
const DIMENSION_LABELS: Record<string, string> = {
  opportunity: '机会',
  method: '手段',
  motive: '动机',
  contradiction: '矛盾',
  identity: '身份',
  causality: '因果',
}
const THEORY_DIMENSIONS: Array<keyof TheoryMap> = ['motive', 'method', 'opportunity']
const PRESSURE_LABELS: Record<string, string> = {
  CALM: '平静',
  GUARDED: '戒备',
  DEFENSIVE: '防御',
  UNSTEADY: '动摇',
}
const KIND_LABELS: Record<string, string> = {
  TESTIMONY: '口供',
  DIGITAL_RECORD: '数字记录',
  PHYSICAL_EVIDENCE: '现场物证',
  WITNESS_OBSERVATION: '目击补述',
  ANALYSIS_RESULT: '分析结果',
}
const LIE_STATUS_LABELS = { CAUGHT: '已识破', HEARD: '听过但遗漏', MISSED: '未发现' }

type Screen = 'home' | 'loading' | 'game'
type IntelTab = 'evidence' | 'timeline' | 'notebook' | 'brief'
type EvidenceFilter = 'ALL' | EvidenceState

function LogoMark() {
  return (
    <div className="logo-mark" aria-hidden="true">
      <span className="logo-mark__ring" />
      <Fingerprint size={19} strokeWidth={1.7} />
    </div>
  )
}

function HomeScreen({
  onStart,
  onResume,
  hasSavedCase,
}: {
  onStart: () => void
  onResume: () => void
  hasSavedCase: boolean
}) {
  return (
    <main className="home-shell">
      <div className="noise-layer" />
      <nav className="home-nav">
        <div className="brand-lockup">
          <LogoMark />
          <div>
            <span className="brand-lockup__name">AI DETECTIVE</span>
            <span className="brand-lockup__sub">CASE ARCHIVE / V2</span>
          </div>
        </div>
        <div className="system-seal"><CircleDot size={12} /> TRUTH DB ONLINE</div>
      </nav>

      <section className="hero">
        <div className="hero__eyebrow">
          <span>事实驱动调查系统</span><span className="hero__rule" /><span>CASE NO. ∞</span>
        </div>
        <h1>每个人都在说话。<br /><em>只有事实不会。</em></h1>
        <p className="hero__lead">
          审问嫌疑人、调取原始记录、核验口供来源。<br className="desktop-only" />
          NPC 可以隐瞒和撒谎，但每一句事实都受世界状态约束。
        </p>
        <div className="hero__actions">
          <button className="button button--primary button--large" onClick={onStart}>
            <Search size={19} />开始新案件<ArrowRight size={18} />
          </button>
          {hasSavedCase && (
            <button className="button button--ghost button--large" onClick={onResume}>
              <FolderOpen size={19} />继续上次调查
            </button>
          )}
        </div>

        <div className="case-preview" aria-label="V2 案件机制预览">
          <div className="case-preview__stamp">CONFIDENTIAL</div>
          <div className="case-preview__header"><span>V2 调查协议</span><span>WORLD STATE / LOCKED</span></div>
          <div className="case-preview__flow">
            <Feature icon={<Database size={20} />} index="01" title="精准问答">
              系统先理解时间、人物和证据，再让 NPC 作答。
            </Feature>
            <ChevronRight className="flow-arrow" size={18} />
            <Feature icon={<ClipboardList size={20} />} index="02" title="可信取证">
              口供只是线索；调取来源后，才能成为已核验证据。
            </Feature>
            <ChevronRight className="flow-arrow" size={18} />
            <Feature icon={<Gavel size={20} />} index="03" title="理论指控">
              用动机、手段与机会构建证据链，而不是只猜名字。
            </Feature>
          </div>
        </div>
      </section>
      <footer className="home-footer">
        <span>TRUTH-BOUND DIALOGUE ENGINE</span>
        <span className="home-footer__center">事实固定 · 来源可查 · 口供可疑</span>
        <span>V2 / 2026</span>
      </footer>
    </main>
  )
}

function Feature({ icon, index, title, children }: {
  icon: React.ReactNode
  index: string
  title: string
  children: React.ReactNode
}) {
  return (
    <article className="feature">
      <div className="feature__top"><span className="feature__icon">{icon}</span><span className="feature__index">{index}</span></div>
      <h2>{title}</h2><p>{children}</p>
    </article>
  )
}

function LoadingScreen({ onCancel }: { onCancel: () => void }) {
  const stages = useMemo(
    () => ['分配已校验案件', '构建人物知识边界', '验证证据发现路径', '封存世界事实'],
    [],
  )
  const [stage, setStage] = useState(0)
  useEffect(() => {
    const timer = window.setInterval(() => setStage((value) => Math.min(value + 1, 3)), 2800)
    return () => window.clearInterval(timer)
  }, [])
  return (
    <main className="loading-screen">
      <div className="loading-grid" />
      <div className="loading-card">
        <div className="loading-seal"><LoaderCircle size={38} /><span>{String(stage + 1).padStart(2, '0')}</span></div>
        <p className="loading-card__kicker">CASE VALIDATION IN PROGRESS</p>
        <h1>{stages[stage]}</h1>
        <p>只有通过时间、证据与可解性校验的案件才会进入调查桌。</p>
        <div className="loading-progress">
          {stages.map((item, index) => (
            <div className={index <= stage ? 'is-active' : ''} key={item}>
              <span>{index < stage ? <Check size={12} /> : index + 1}</span>{item}
            </div>
          ))}
        </div>
        <button className="text-button" onClick={onCancel}><ArrowLeft size={15} /> 返回首页</button>
      </div>
    </main>
  )
}

function mergeSuspectStats(suspects: Suspect[], notebook: Notebook): Suspect[] {
  const byId = new Map(notebook.suspect_summaries.map((item) => [item.npc_id, item]))
  return suspects.map((suspect) => ({ ...suspect, ...(byId.get(suspect.id) ?? {}) }))
}

function InvestigationScreen({ game, onGameChange, onHome }: {
  game: GameState
  onGameChange: (next: GameState) => void
  onHome: () => void
}) {
  const [selectedNpcId, setSelectedNpcId] = useState(game.suspects[0]?.id ?? '')
  const [question, setQuestion] = useState('')
  const [contextTime, setContextTime] = useState('')
  const [quotedEntry, setQuotedEntry] = useState<DialogueEntry | null>(null)
  const [clarifications, setClarifications] = useState<string[]>([])
  const [submitting, setSubmitting] = useState(false)
  const [investigatingId, setInvestigatingId] = useState('')
  const [error, setError] = useState('')
  const [newEvidenceNotice, setNewEvidenceNotice] = useState<Evidence | null>(null)
  const [intelTab, setIntelTab] = useState<IntelTab>('evidence')
  const [evidenceFilter, setEvidenceFilter] = useState<EvidenceFilter>('ALL')
  const [presentedEvidenceIds, setPresentedEvidenceIds] = useState<string[]>([])
  const [accusationOpen, setAccusationOpen] = useState(false)
  const [mobilePanelOpen, setMobilePanelOpen] = useState(false)
  const [mobileIntelOpen, setMobileIntelOpen] = useState(false)
  const chatEndRef = useRef<HTMLDivElement>(null)

  const selectedNpc = game.suspects.find((item) => item.id === selectedNpcId) ?? game.suspects[0]
  const selectedMessages = game.messages.filter((item) => item.npc_id === selectedNpc?.id)

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  }, [selectedMessages.length, submitting])
  useEffect(() => {
    if (!newEvidenceNotice) return
    const timer = window.setTimeout(() => setNewEvidenceNotice(null), 4600)
    return () => window.clearTimeout(timer)
  }, [newEvidenceNotice])

  const ask = useCallback(async (suggested?: string) => {
    const rawValue = (suggested ?? question).trim()
    if (!rawValue || !selectedNpc || submitting || game.actions_remaining <= 0) return
    const value = quotedEntry && !rawValue.includes('你刚才')
      ? `你刚才说“${quotedEntry.response}”。${rawValue}`
      : rawValue
    setSubmitting(true)
    setError('')
    setClarifications([])
    try {
      const response = await gameApi.interrogate(game.case_id, {
        npc_id: selectedNpc.id,
        question: value,
        presented_evidence_ids: presentedEvidenceIds,
        context_time: contextTime || null,
        request_id: crypto.randomUUID(),
      })
      if (response.status === 'NEEDS_CLARIFICATION' || !response.entry) {
        setClarifications(response.clarification_options)
        setError('这句话可能有多种理解。请选择一个更具体的问法；本次未消耗调查额度。')
        return
      }
      const evidenceById = new Map(game.evidence.map((item) => [item.id, item]))
      response.new_evidence.forEach((item) => evidenceById.set(item.id, item))
      onGameChange({
        ...game,
        messages: [...game.messages, response.entry],
        evidence: [...evidenceById.values()],
        suspects: mergeSuspectStats(game.suspects, response.notebook),
        notebook: response.notebook,
        actions_remaining: response.actions_remaining,
        questions_remaining: response.actions_remaining,
      })
      setQuestion('')
      setContextTime('')
      setQuotedEntry(null)
      setPresentedEvidenceIds([])
      if (response.new_evidence[0]) {
        setNewEvidenceNotice(response.new_evidence[0])
        setIntelTab('evidence')
      }
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : '审问请求失败，本次不会扣除调查额度。')
    } finally {
      setSubmitting(false)
    }
  }, [contextTime, game, onGameChange, presentedEvidenceIds, question, quotedEntry, selectedNpc, submitting])

  const investigate = async (item: Evidence) => {
    if (!item.action_type || investigatingId || game.actions_remaining <= 0) return
    setInvestigatingId(item.id)
    setError('')
    try {
      const response = await gameApi.investigate(game.case_id, {
        evidence_id: item.id,
        action_type: item.action_type,
        request_id: crypto.randomUUID(),
      })
      onGameChange({
        ...game,
        evidence: game.evidence.map((current) => current.id === item.id ? response.evidence : current),
        suspects: mergeSuspectStats(game.suspects, response.notebook),
        notebook: response.notebook,
        actions_remaining: response.actions_remaining,
        questions_remaining: response.actions_remaining,
      })
      setNewEvidenceNotice(response.evidence)
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : '来源核验失败，本次不会扣除调查额度。')
    } finally {
      setInvestigatingId('')
    }
  }

  const presentEvidence = (evidenceId: string) => {
    const item = game.evidence.find((evidence) => evidence.id === evidenceId)
    if (!item?.usable_in_accusation) return
    setPresentedEvidenceIds([evidenceId])
    setQuestion(`关于“${item.title}”，你怎么解释？`)
  }

  return (
    <main className="app-shell">
      <header className="app-header">
        <button className="brand-button" onClick={onHome} aria-label="返回首页">
          <LogoMark /><span><b>AI DETECTIVE</b><small>INVESTIGATION DESK / V2</small></span>
        </button>
        <div className="app-header__case">
          <span>CASE</span><b>#{game.case_id.slice(0, 8).toUpperCase()}</b>
          <span className="locked-chip"><LockKeyhole size={12} /> WORLD LOCKED</span>
        </div>
        <div className="app-header__actions">
          <div className="question-counter" aria-label={`剩余 ${game.actions_remaining} 点调查额度`}>
            <span>调查额度</span><b>{String(game.actions_remaining).padStart(2, '0')}</b><small>/ {game.action_limit}</small>
          </div>
          <button className="button button--accent" onClick={() => setAccusationOpen(true)}>
            <Gavel size={17} /> 构建指控
          </button>
          <button className="icon-button mobile-only mobile-evidence-button" onClick={() => {
            setMobileIntelOpen((value) => !value); setMobilePanelOpen(false)
          }} aria-label="查看案件板"><Fingerprint size={20} /></button>
          <button className="icon-button mobile-only" onClick={() => {
            setMobilePanelOpen((value) => !value); setMobileIntelOpen(false)
          }} aria-label="切换嫌疑人"><Menu size={20} /></button>
        </div>
      </header>

      <div className="case-strip">
        <div><span className="case-strip__label">当前案件</span><h1>{game.brief.title}</h1></div>
        <div className="case-strip__fact"><UserRoundSearch size={16} /><span>死者</span><b>{game.brief.victim.name}</b></div>
        <div className="case-strip__fact"><MapPin size={16} /><span>地点</span><b>{game.brief.location}</b></div>
        <div className="case-strip__fact"><Clock3 size={16} /><span>死亡窗口</span><b>{game.brief.death_window}</b></div>
      </div>

      <div className="investigation-grid investigation-grid--v2">
        <aside className={`suspect-rail ${mobilePanelOpen ? 'is-mobile-open' : ''}`}>
          <div className="panel-heading"><span>嫌疑人 / 04</span><UsersRound size={16} /></div>
          <div className="suspect-list">
            {game.suspects.map((suspect, index) => (
              <button className={`suspect-card ${suspect.id === selectedNpc?.id ? 'is-active' : ''}`} key={suspect.id}
                onClick={() => { setSelectedNpcId(suspect.id); setMobilePanelOpen(false); setQuotedEntry(null) }}>
                <span className="suspect-card__number">0{index + 1}</span>
                <span className="suspect-avatar">{suspect.initials}</span>
                <span className="suspect-card__copy">
                  <b>{suspect.name}</b><small>{suspect.role}</small>
                  <span className="suspect-card__signals">
                    <i>{suspect.interview_count} 次审问</i>
                    {suspect.contradiction_count > 0 && <i className="is-alert">{suspect.contradiction_count} 处冲突</i>}
                  </span>
                </span>
                <span className={`pressure-dot pressure-dot--${suspect.pressure_state.toLowerCase()}`} title={PRESSURE_LABELS[suspect.pressure_state]} />
                <ChevronRight size={16} />
              </button>
            ))}
          </div>
          <div className="rail-note"><ShieldCheck size={16} /><p>世界事实已封存。<br />口供、线索与证据分开记录。</p></div>
        </aside>

        <section className="interview-panel">
          <header className="interview-header">
            <div className="interview-identity">
              <span className="suspect-avatar suspect-avatar--large">{selectedNpc?.initials}</span>
              <div>
                <span className="interview-header__label">INTERROGATION / 正在审问</span>
                <h2>{selectedNpc?.name}</h2>
                <p>{selectedNpc?.role} · {selectedNpc?.personality}</p>
              </div>
            </div>
            <span className="live-dot"><i /> {PRESSURE_LABELS[selectedNpc?.pressure_state ?? 'CALM']} / RECORDING</span>
          </header>

          <div className="chat-log" aria-live="polite">
            {selectedMessages.length === 0 ? (
              <EmptyInterview suspect={selectedNpc} onAsk={(value) => void ask(value)} />
            ) : selectedMessages.map((entry, index) => (
              <DialogueBubble key={entry.id} entry={entry} suspect={selectedNpc} index={index + 1}
                evidence={game.evidence} onFollowup={(value) => void ask(value)} onQuote={() => {
                  setQuotedEntry(entry); setQuestion('这与你现在的说法一致吗？')
                }} />
            ))}
            {submitting && <div className="npc-reply npc-reply--thinking"><span className="bubble-label">{selectedNpc?.name}</span><div className="thinking-dots"><i /><i /><i /></div></div>}
            <div ref={chatEndRef} />
          </div>

          <div className="composer-area composer-area--v2">
            {error && <div className="inline-error"><AlertCircle size={15} /> {error}</div>}
            {clarifications.length > 0 && (
              <div className="clarification-options" role="status">
                {clarifications.map((item) => <button key={item} onClick={() => void ask(item)}>{item}<ArrowRight size={12} /></button>)}
              </div>
            )}
            <div className="context-chips">
              <label><Clock3 size={13} /><input value={contextTime} onChange={(event) => setContextTime(event.target.value.slice(0, 32))} placeholder="补充时间，如 20:00 左右" /></label>
              {quotedEntry && <span><Quote size={12} /> 已引用上一条口供<button onClick={() => setQuotedEntry(null)} aria-label="取消引用"><X size={12} /></button></span>}
              {presentedEvidenceIds.map((id) => <span key={id}><KeyRound size={12} /> {game.evidence.find((item) => item.id === id)?.title}<button onClick={() => setPresentedEvidenceIds([])} aria-label="取消出示"><X size={12} /></button></span>)}
            </div>
            <div className="composer">
              <textarea value={question} onChange={(event) => setQuestion(event.target.value.slice(0, 500))}
                onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); void ask() } }}
                placeholder={game.actions_remaining > 0 ? `问 ${selectedNpc?.name} 一个具体问题…` : '调查额度已用完，请构建指控。'}
                disabled={submitting || game.actions_remaining <= 0} rows={2} />
              <div className="composer__footer"><span>ENTER 发送 · 系统误解与请求失败不扣额度</span>
                <button className="send-button" onClick={() => void ask()} disabled={!question.trim() || submitting || game.actions_remaining <= 0} aria-label="发送问题">
                  {submitting ? <LoaderCircle className="spin" size={18} /> : <Send size={18} />}
                </button>
              </div>
            </div>
          </div>
        </section>

        <aside className={`intel-panel ${mobileIntelOpen ? 'is-mobile-open' : ''}`}>
          <div className="intel-tabs intel-tabs--v2" role="tablist">
            <button className={intelTab === 'evidence' ? 'is-active' : ''} onClick={() => setIntelTab('evidence')}><Fingerprint size={15} /> 资料 <span>{game.evidence.length}</span></button>
            <button className={intelTab === 'timeline' ? 'is-active' : ''} onClick={() => setIntelTab('timeline')}><Clock3 size={15} /> 时间线</button>
            <button className={intelTab === 'notebook' ? 'is-active' : ''} onClick={() => setIntelTab('notebook')}><ClipboardList size={15} /> 矛盾 <span>{game.notebook.contradictions.length}</span></button>
            <button className={intelTab === 'brief' ? 'is-active' : ''} onClick={() => setIntelTab('brief')}><BookOpen size={15} /> 案情</button>
          </div>
          <div className="intel-content">
            <button className="mobile-intel-close mobile-only" onClick={() => setMobileIntelOpen(false)}><X size={15} /> 关闭案件面板</button>
            {intelTab === 'evidence' && <EvidenceBoard evidence={game.evidence} filter={evidenceFilter} onFilter={setEvidenceFilter}
              onPresent={presentEvidence} onInvestigate={(item) => void investigate(item)} investigatingId={investigatingId} />}
            {intelTab === 'timeline' && <Timeline items={game.notebook.timeline_entries} />}
            {intelTab === 'notebook' && <NotebookPanel game={game} />}
            {intelTab === 'brief' && <Briefing game={game} />}
          </div>
        </aside>
      </div>

      {newEvidenceNotice && <div className="evidence-toast" role="status">
        <span className="evidence-toast__icon">{newEvidenceNotice.verification_state === 'VERIFIED' ? <BadgeCheck size={18} /> : <Sparkles size={18} />}</span>
        <div><small>{newEvidenceNotice.verification_state === 'VERIFIED' ? 'SOURCE VERIFIED / 来源已核验' : 'NEW LEAD / 新线索待核验'}</small><b>{newEvidenceNotice.title}</b></div>
        <button onClick={() => setNewEvidenceNotice(null)} aria-label="关闭"><X size={14} /></button>
      </div>}

      {accusationOpen && <AccusationModal game={game} onClose={() => setAccusationOpen(false)}
        onReview={(review) => onGameChange({ ...game, status: 'REVIEWED', review_used: true, review })}
        onResult={(result) => {
          onGameChange({ ...game, status: result.outcome === 'SOLVED' ? 'SOLVED' : 'FAILED', result })
          setAccusationOpen(false)
        }} />}
    </main>
  )
}

function EmptyInterview({ suspect, onAsk }: { suspect?: Suspect; onAsk: (value: string) => void }) {
  return <div className="empty-interview">
    <span className="empty-interview__index">START / 00</span><div className="empty-interview__portrait">{suspect?.initials}</div>
    <h3>{suspect?.name} 已坐在审讯桌前</h3><p>{suspect?.public_bio}</p>
    <div className="question-suggestions"><span>可以这样开始</span>{EXAMPLE_QUESTIONS.map((item) => <button key={item} onClick={() => onAsk(item)}>“{item}” <ArrowRight size={13} /></button>)}</div>
  </div>
}

function DialogueBubble({ entry, suspect, index, evidence, onFollowup, onQuote }: {
  entry: DialogueEntry
  suspect?: Suspect
  index: number
  evidence: Evidence[]
  onFollowup: (value: string) => void
  onQuote: () => void
}) {
  const unlocked = entry.discovered_evidence_ids.map((id) => evidence.find((item) => item.id === id)).filter(Boolean) as Evidence[]
  return <article className="dialogue-exchange">
    <div className="player-question"><span className="bubble-label">YOU / Q{String(index).padStart(2, '0')}</span><p>{entry.question}</p></div>
    <div className={`npc-reply npc-reply--${entry.reaction.toLowerCase()}`}>
      <div className="reply-meta"><span className="bubble-label">{suspect?.name}</span><span>{entry.understanding}</span></div>
      <p>{entry.response}</p>
      {entry.coverage === 'PARTIAL' && <span className="coverage-warning"><TriangleAlert size={12} /> NPC 只部分回答了所问范围</span>}
      {unlocked.map((item) => <span className="unlocked-inline" key={item.id}><Fingerprint size={13} /> 新线索：{item.title} · 待核验来源</span>)}
      <div className="reply-actions"><button onClick={onQuote}><Quote size={12} /> 引用这段口供</button>{entry.suggested_followups.slice(0, 2).map((item) => <button key={item} onClick={() => onFollowup(item)}>{item}<ArrowRight size={11} /></button>)}</div>
    </div>
  </article>
}

function EvidenceBoard({ evidence, filter, onFilter, onPresent, onInvestigate, investigatingId }: {
  evidence: Evidence[]
  filter: EvidenceFilter
  onFilter: (value: EvidenceFilter) => void
  onPresent: (id: string) => void
  onInvestigate: (item: Evidence) => void
  investigatingId: string
}) {
  const filtered = filter === 'ALL' ? evidence : evidence.filter((item) => item.verification_state === filter)
  if (evidence.length === 0) return <div className="empty-intel"><FileQuestion size={28} /><h3>还没有资料</h3><p>从具体时间、地点和异常记录开始询问。</p></div>
  return <div className="evidence-list">
    <div className="intel-intro"><span>案件资料 {String(evidence.length).padStart(2, '0')} 件</span><p>未核实线索不能用于指控，先调取原始来源。</p></div>
    <div className="evidence-filters"><Filter size={13} />{([['ALL', '全部'], ['UNVERIFIED', '未核实'], ['VERIFIED', '已核验'], ['CONTESTED', '有冲突']] as Array<[EvidenceFilter, string]>).map(([value, label]) => <button className={filter === value ? 'is-active' : ''} key={value} onClick={() => onFilter(value)}>{label}</button>)}</div>
    {filtered.map((item, index) => <article className={`evidence-card evidence-card--${item.verification_state.toLowerCase()}`} key={item.id}>
      <div className="evidence-card__top"><span className="evidence-card__number">E-{String(index + 1).padStart(2, '0')} · {KIND_LABELS[item.kind] ?? item.kind}</span><span className="evidence-card__status">{item.verification_state === 'VERIFIED' ? <Check size={11} /> : <AlertCircle size={11} />}{item.status}</span></div>
      <h3>{item.title}</h3><p>{item.description}</p>
      <div className="dimension-row">{item.dimensions.map((dimension) => <span key={dimension}>{DIMENSION_LABELS[dimension] ?? dimension}</span>)}</div>
      <div className="evidence-card__footer"><span>来源：{item.source}</span>
        {item.verification_state === 'UNVERIFIED' ? <button onClick={() => onInvestigate(item)} disabled={investigatingId === item.id}>{investigatingId === item.id ? <LoaderCircle className="spin" size={12} /> : <Search size={12} />}{item.action_label}</button> : <button onClick={() => onPresent(item.id)}>出示质询 <ArrowRight size={12} /></button>}
      </div>
    </article>)}
  </div>
}

function Timeline({ items }: { items: Array<{ time: string; event: string; status?: string }> }) {
  return <div className="timeline"><div className="intel-intro"><span>案件与口供时间线</span><p>口供节点不等于已验证事实。</p></div>{items.map((item, index) => <div className={`timeline-item ${item.status === 'TESTIMONY' ? 'is-testimony' : ''}`} key={`${item.time}-${index}`}><span className="timeline-item__dot" /><time>{item.time}</time><p>{item.event}</p></div>)}</div>
}

function NotebookPanel({ game }: { game: GameState }) {
  return <div className="notebook-panel"><div className="intel-intro"><span>自动调查笔记</span><p>系统只指出可能冲突，不判断哪一方为真。</p></div>
    {game.notebook.contradictions.length === 0 ? <div className="empty-intel"><ClipboardList size={28} /><h3>尚未形成矛盾</h3><p>核验记录并引用旧口供继续追问。</p></div> : game.notebook.contradictions.map((item) => <article className="contradiction-card" key={item.id}><TriangleAlert size={15} /><div><b>{game.suspects.find((suspect) => suspect.id === item.npc_id)?.name}</b><p>{item.label}</p><small>“{item.claim}”</small></div></article>)}
  </div>
}

function Briefing({ game }: { game: GameState }) {
  return <div className="briefing"><div className="briefing__classification">RESTRICTED / V2 调查员权限</div><h3>{game.brief.title}</h3><p>{game.brief.summary}</p><dl>
    <div><dt>机构</dt><dd>{game.brief.setting}</dd></div><div><dt>死者</dt><dd>{game.brief.victim.name} · {game.brief.victim.role}</dd></div>
    <div><dt>地点</dt><dd>{game.brief.location}</dd></div><div><dt>引擎</dt><dd>Truth-bound Dialogue / Schema {game.schema_version}</dd></div>
  </dl><div className="briefing__warning"><AlertCircle size={15} />NPC 可以隐瞒与本案无关的秘密。口供为假，不等于此人就是凶手。</div></div>
}

function AccusationModal({ game, onClose, onReview, onResult }: {
  game: GameState
  onClose: () => void
  onReview: (review: AccusationReview) => void
  onResult: (result: AccusationResult) => void
}) {
  const [suspectId, setSuspectId] = useState('')
  const [theory, setTheory] = useState<TheoryMap>({ motive: [], method: [], opportunity: [] })
  const [reasoning, setReasoning] = useState('')
  const [review, setReview] = useState<AccusationReview | null>(game.review)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const closeRef = useRef<HTMLButtonElement>(null)
  const verifiedEvidence = game.evidence.filter((item) => item.usable_in_accusation)
  const ready = Boolean(suspectId) && THEORY_DIMENSIONS.every((dimension) => theory[dimension].length > 0)

  useEffect(() => {
    closeRef.current?.focus()
    const onKeyDown = (event: KeyboardEvent) => { if (event.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [onClose])

  const toggleTheory = (dimension: keyof TheoryMap, id: string) => {
    setTheory((current) => {
      const values = current[dimension]
      return { ...current, [dimension]: values.includes(id) ? values.filter((item) => item !== id) : values.length < 2 ? [...values, id] : values }
    })
  }
  const requestReview = async () => {
    if (!ready || game.review_used || submitting) return
    setSubmitting(true); setError('')
    try {
      const value = await gameApi.reviewAccusation(game.case_id, { suspect_id: suspectId, theory, request_id: crypto.randomUUID() })
      setReview(value); onReview(value)
    } catch (caught) { setError(caught instanceof ApiError ? caught.message : '预审失败，请稍后重试。') }
    finally { setSubmitting(false) }
  }
  const submit = async () => {
    if (!ready || submitting) return
    setSubmitting(true); setError('')
    try {
      const result = await gameApi.accuse(game.case_id, {
        suspect_id: suspectId,
        evidence_ids: [...new Set(Object.values(theory).flat())],
        theory,
        reasoning_text: reasoning,
        request_id: crypto.randomUUID(),
      })
      onResult(result)
    } catch (caught) { setError(caught instanceof ApiError ? caught.message : '指控提交失败，请稍后重试。'); setSubmitting(false) }
  }

  return <div className="modal-backdrop" role="presentation" onMouseDown={onClose}><section className="accusation-modal accusation-modal--v2" role="dialog" aria-modal="true" aria-labelledby="accusation-title" onMouseDown={(event) => event.stopPropagation()}>
    <header className="modal-header"><div><span>CASE THEORY / 指控理论</span><h2 id="accusation-title">把动机、手段与机会闭合</h2></div><button ref={closeRef} className="icon-button" onClick={onClose} aria-label="关闭指控窗口"><X size={19} /></button></header>
    <div className="accusation-body">
      <div className="accusation-step"><span className="step-number">01</span><div className="step-content"><h3>你指控谁？</h3><p>预审不会告诉你嫌疑人是否选对。</p><div className="accused-grid">{game.suspects.map((suspect) => <button className={suspectId === suspect.id ? 'is-selected' : ''} key={suspect.id} onClick={() => setSuspectId(suspect.id)}><span>{suspect.initials}</span><b>{suspect.name}</b><small>{suspect.role}</small><i>{suspectId === suspect.id && <Check size={13} />}</i></button>)}</div></div></div>
      <div className="accusation-step"><span className="step-number">02</span><div className="step-content"><h3>构建三段证明链</h3><p>每个维度选择 1–2 条已核验证据；同一证据可承担多个维度。</p><div className="theory-builder">{THEORY_DIMENSIONS.map((dimension) => <section key={dimension}><header><span>{DIMENSION_LABELS[dimension]}</span><small>{theory[dimension].length}/2</small></header><div>{verifiedEvidence.map((item) => { const selected = theory[dimension].includes(item.id); const supports = item.dimensions.includes(dimension); return <button className={`${selected ? 'is-selected' : ''} ${supports ? '' : 'is-weak'}`} key={item.id} onClick={() => toggleTheory(dimension, item.id)}><i>{selected && <Check size={11} />}</i><span><b>{item.title}</b><small>{supports ? `可支持${DIMENSION_LABELS[dimension]}` : '关联较弱'}</small></span></button> })}</div></section>)}</div></div></div>
      <div className="accusation-step"><span className="step-number">03</span><div className="step-content"><h3>结案陈词 <small>可选</small></h3><p>用于生成个性化复盘；最终对错仍由确定性规则判定。</p><textarea rows={3} maxLength={1200} value={reasoning} onChange={(event) => setReasoning(event.target.value)} placeholder="写下你的推理……" /></div></div>
      {review && <div className="review-panel" role="status"><span>PROSECUTOR REVIEW / 检方预审</span><div className="review-coverage">{THEORY_DIMENSIONS.map((dimension) => <i className={review.coverage[dimension] ? 'is-covered' : ''} key={dimension}>{review.coverage[dimension] ? <Check size={12} /> : <AlertCircle size={12} />}{DIMENSION_LABELS[dimension]}</i>)}</div>{review.feedback.map((item) => <p key={item}>{item}</p>)}</div>}
    </div>
    <footer className="modal-footer"><div>{error ? <span className="modal-error"><AlertCircle size={14} /> {error}</span> : <span><LockKeyhole size={13} /> 最终提交后才会揭露真相。</span>}</div><button className="button button--ghost" disabled={!ready || game.review_used || submitting} onClick={() => void requestReview()}>{game.review_used ? '预审已使用' : '检方预审'}</button><button className="button button--danger" disabled={!ready || submitting} onClick={() => void submit()}>{submitting ? <LoaderCircle className="spin" size={17} /> : <Gavel size={17} />} 最终指控</button></footer>
  </section></div>
}

function ResultScreen({ game, onNewCase, onHome }: { game: GameState; onNewCase: () => void; onHome: () => void }) {
  const result = game.result
  if (!result) return null
  const solved = result.outcome === 'SOLVED'
  return <main className={`result-screen result-screen--${result.outcome.toLowerCase()}`}><div className="noise-layer" />
    <header className="result-nav"><div className="brand-lockup"><LogoMark /><div><span className="brand-lockup__name">AI DETECTIVE</span><span className="brand-lockup__sub">CASE CLOSED / V2</span></div></div><span>#{game.case_id.slice(0, 8).toUpperCase()}</span></header>
    <section className="result-hero result-hero--v2"><div className="result-seal">{solved ? <ShieldCheck size={34} /> : <AlertCircle size={34} />}</div><span className="result-hero__kicker">VERDICT / 系统裁决</span><h1>{result.headline}</h1><p>{result.explanation}</p><div className="culprit-reveal"><span>真正的凶手</span><b>{result.culprit_name}</b><small>{game.suspects.find((item) => item.id === result.culprit_id)?.role}</small></div></section>
    <section className="result-dossier">
      <article className="player-case-review"><span className="section-kicker">01 / 你的证据链</span><h2>哪里成立，哪里断裂</h2>{result.missing_dimensions.length > 0 && <div className="missing-chain"><AlertCircle size={16} /><span>仍缺：{result.missing_dimensions.join('、')}</span></div>}<div className="evidence-analysis-grid">{result.evidence_analysis.map((item) => <div key={item.evidence_id}><span>{item.mapped_to.map((dimension) => DIMENSION_LABELS[dimension] ?? dimension).join(' / ') || '未映射'}</span><b>{item.title}</b><small>{item.dimensions.map((dimension) => DIMENSION_LABELS[dimension] ?? dimension).join(' · ')}</small></div>)}</div></article>
      <article className="truth-summary"><span className="section-kicker">02 / 案件真相</span><h2>封存事实还原</h2><p>{result.truth_summary}</p><div className="truth-facts"><div><FlaskConical size={18} /><span>作案手段</span><p>{result.method}</p></div><div><CircleDot size={18} /><span>作案动机</span><p>{result.motive}</p></div></div></article>
      <article className="truth-timeline"><span className="section-kicker">03 / 真实时间线</span><h2>当晚发生了什么</h2><div>{result.truth_timeline.map((item, index) => <div className="truth-timeline__item" key={`${item.time}-${index}`}><time>{item.time}</time><span /><p>{item.event}</p></div>)}</div></article>
      <article className="lies-review"><span className="section-kicker">04 / 调查对照</span><h2>你识破了哪些谎言</h2><div className="lies-grid">{result.key_lies.slice(0, 8).map((item) => <details key={item.claim_id}><summary><span>{item.speaker}</span><p>“{item.claim}”</p><i className={`lie-status lie-status--${item.discovery_status.toLowerCase()}`}>{LIE_STATUS_LABELS[item.discovery_status]}</i><Plus size={15} /></summary><div><b>真实情况</b><p>{item.truth}</p></div></details>)}</div></article>
    </section>
    <footer className="result-actions"><button className="button button--ghost button--large" onClick={onHome}><ArrowLeft size={17} /> 返回档案室</button><button className="button button--primary button--large" onClick={onNewCase}><RotateCcw size={17} /> 再来一案</button></footer>
  </main>
}

export default function App() {
  const [screen, setScreen] = useState<Screen>('home')
  const [game, setGame] = useState<GameState | null>(null)
  const [savedCaseId, setSavedCaseId] = useState(() => localStorage.getItem(STORAGE_KEY))
  const [fatalError, setFatalError] = useState('')
  const updateGame = useCallback((next: GameState) => {
    setGame(next); localStorage.setItem(STORAGE_KEY, next.case_id); setSavedCaseId(next.case_id)
  }, [])
  const startCase = useCallback(async () => {
    setScreen('loading'); setFatalError('')
    try { const next = await gameApi.createCase(); updateGame(next); setScreen('game') }
    catch (caught) { setFatalError(caught instanceof ApiError ? caught.message : '案件生成失败，请确认服务已经启动。'); setScreen('home') }
  }, [updateGame])
  const resumeCase = useCallback(async () => {
    if (!savedCaseId) return
    setScreen('loading'); setFatalError('')
    try { const next = await gameApi.getCase(savedCaseId); updateGame(next); setScreen('game') }
    catch (caught) { localStorage.removeItem(STORAGE_KEY); setSavedCaseId(null); setFatalError(caught instanceof ApiError ? caught.message : '无法恢复上次案件。'); setScreen('home') }
  }, [savedCaseId, updateGame])
  if (screen === 'loading') return <LoadingScreen onCancel={() => setScreen('home')} />
  if (screen === 'game' && game?.result) return <ResultScreen game={game} onNewCase={() => void startCase()} onHome={() => setScreen('home')} />
  if (screen === 'game' && game) return <InvestigationScreen game={game} onGameChange={updateGame} onHome={() => setScreen('home')} />
  return <><HomeScreen onStart={() => void startCase()} onResume={() => void resumeCase()} hasSavedCase={Boolean(savedCaseId)} />{fatalError && <div className="fatal-toast" role="alert"><AlertCircle size={17} /><span>{fatalError}</span><button onClick={() => setFatalError('')} aria-label="关闭错误提示"><X size={15} /></button></div>}</>
}
