"use client";

import { useEffect, useState } from "react";
import MarketChart from "@/components/MarketChart";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";

const navItems = [
  { icon: "◈", label: "市场总览", tag: "01" },
  { icon: "⌁", label: "Market Scanner", tag: "02" },
  { icon: "◎", label: "AI Intelligence", tag: "03" },
  { icon: "▤", label: "News Radar", tag: "04" },
  { icon: "⌗", label: "Coin Explorer", tag: "05" },
  { icon: "↗", label: "预测表现", tag: "06" },
];



export default function Home() {
  const [activeNav, setActiveNav] = useState("市场总览");
  const [search, setSearch] = useState("");
  const [coins, setCoins] = useState<any[]>([]);
  const [dbStats, setDbStats] = useState({ coins: 0, snapshots: 0 });
  const [runs, setRuns] = useState<any[]>([]);
  const [aiOnline, setAiOnline] = useState(false);
  const [apiOnline, setApiOnline] = useState(false);
  const [marketOnline, setMarketOnline] = useState(false);
  const [lastUpdated, setLastUpdated] = useState("");

  useEffect(() => {
    let active = true;

    const getJson = async (path: string) => {
      const response = await fetch(
        API_BASE_URL + path,
        { cache: "no-store" }
      );
      if (!response.ok) {
        throw new Error("HTTP " + response.status);
      }
      return response.json();
    };

    const pickNumber = (obj: any, keys: string[]) => {
      for (const key of keys) {
        const value = Number(obj?.[key]);
        if (Number.isFinite(value)) return value;
      }
      return 0;
    };

    async function loadDashboard() {
      const results = await Promise.allSettled([
        getJson("/api/market/coins?per_page=100"),
        getJson("/api/market/database"),
        getJson("/api/market/collection-runs?limit=5"),
        getJson("/api/ai/status")
      ]);

      if (!active) return;

      if (results[0].status === "fulfilled") {
        const payload = results[0].value;
        const list = Array.isArray(payload)
          ? payload
          : payload.data || payload.coins || payload.results || [];
        setCoins(Array.isArray(list) ? list : []);
        setMarketOnline(true);
      } else {
        setMarketOnline(false);
      }

      if (results[1].status === "fulfilled") {
        const db = results[1].value;
        setDbStats({
          coins: pickNumber(db, [
            "coins", "total_coins", "coin_count", "assets"
          ]),
          snapshots: pickNumber(db, [
            "snapshots", "total_snapshots", "snapshot_count", "records"
          ])
        });
        setApiOnline(true);
      } else {
        setApiOnline(false);
      }

      if (results[2].status === "fulfilled") {
        const payload = results[2].value;
        const list = Array.isArray(payload)
          ? payload
          : payload.runs || payload.data || [];
        setRuns(Array.isArray(list) ? list : []);
      }

      if (results[3].status === "fulfilled") {
        const ai = results[3].value;
        const status = String(
          ai.ollama || ai.status || ai.state || ""
        ).toLowerCase();

        setAiOnline(
          status === "connected" ||
          status === "online" ||
          status === "ready" ||
          ai.connected === true ||
          ai.available === true
        );
      } else {
        setAiOnline(false);
      }

      setLastUpdated(new Date().toLocaleTimeString("zh-CN"));
    }

    loadDashboard();
    const timer = window.setInterval(loadDashboard, 30000);

    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, []);

  const filteredCoins = coins.filter((coin: any) =>
    `${coin.symbol || ""} ${coin.name || ""}`
      .toLowerCase()
      .includes(search.toLowerCase())
  );

  const latestRun = runs[0];

  return (
    <main className="radar-app">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark"><span>R</span><i /></div>
          <div>
            <div className="brand-name">CRYPTO<span>RADAR</span></div>
            <div className="brand-sub">AI INTELLIGENCE TERMINAL</div>
          </div>
        </div>

        <div className="side-label">WORKSPACE</div>
        <nav className="nav-list">
          {navItems.map((item) => (
            <button
              key={item.label}
              className={`nav-item ${activeNav === item.label ? "active" : ""}`}
              onClick={() => setActiveNav(item.label)}
            >
              <span className="nav-icon">{item.icon}</span>
              <span>{item.label}</span>
              <small>{item.tag}</small>
            </button>
          ))}
        </nav>

        <div className="sidebar-bottom">
          <div className="system-card">
            <div className="system-heading"><span className="live-dot" /> SYSTEM STATUS</div>
            <div className="system-row"><span>API Backend</span><b className={apiOnline ? "status-green" : "status-yellow"}>{apiOnline ? "READY" : "OFFLINE"}</b></div>
            <div className="system-row"><span>AI Engine</span><b className={aiOnline ? "status-green" : "status-yellow"}>{aiOnline ? "LOCAL" : "OFFLINE"}</b></div>
            <div className="system-row"><span>Market Feed</span><b className={marketOnline ? "status-green" : "status-yellow"}>{marketOnline ? "LIVE" : "CONNECTING"}</b></div>
          </div>
          <div className="profile">
            <div className="avatar">CR</div>
            <div><strong>RADAR SYSTEM</strong><small>Local Environment</small></div>
            <span className="profile-menu">···</span>
          </div>
        </div>
      </aside>

      <section className="main-panel">
        <header className="topbar">
          <div className="breadcrumb">WORKSPACE <span>/</span> <b>{activeNav.toUpperCase()}</b></div>
          <div className="top-actions">
            <div className="system-pill"><span className="live-dot" /> LOCAL SYSTEM ONLINE</div>
            <button className="icon-button" title="通知">♧</button>
            <div className="top-avatar">AI</div>
          </div>
        </header>

        <div className="dashboard-content">
          <section className="welcome-row">
            <div>
              <div className="eyebrow"><span /> CRYPTO MARKET INTELLIGENCE</div>
              <h1>市场<span>总览</span></h1>
              <p className="welcome-desc">洞察市场变化，捕捉潜在机会。让 AI 帮你持续追踪加密市场。</p>
            </div>
            <div className="date-chip"><span>◷</span> LIVE MONITORING <i /></div>
          </section>

          <section className="ticker-strip">
            {coins
              .filter((coin: any) =>
                ["btc", "eth", "bnb", "xrp", "sol"].includes(
                  String(coin.symbol || "").toLowerCase()
                )
              )
              .slice(0, 5)
              .map((coin: any) => {
                const change = Number(coin.price_change_percentage_24h || 0);
                return (
                  <div className="ticker-item" key={coin.symbol}>
                    <div className="ticker-symbol">
                      <b>{String(coin.symbol).toUpperCase()}</b>
                      <small>{coin.name}</small>
                    </div>
                    <strong>
                      ${Number(coin.current_price || 0).toLocaleString("en-US", {
                        maximumFractionDigits: 6
                      })}
                    </strong>
                    <span className={change >= 0 ? "ticker-up" : "ticker-down"}>
                      {change >= 0 ? "+" : ""}{change.toFixed(2)}%
                    </span>
                  </div>
                );
              })}
          </section>

          <section className="metrics-grid">
            <div className="metric-card">
              <div className="metric-top"><span>监控资产</span><span className="metric-icon cyan">◈</span></div>
              <div className="metric-value">{dbStats.coins.toLocaleString()} <small>ASSETS</small></div>
              <div className="metric-foot"><span className="tiny-dot green" /> CoinGecko 市值排名前 250</div>
            </div>
            <div className="metric-card">
              <div className="metric-top"><span>历史行情快照</span><span className="metric-icon purple">▤</span></div>
              <div className="metric-value">{dbStats.snapshots.toLocaleString()} <small>RECORDS</small></div>
              <div className="metric-foot"><span className="tiny-dot green" /> SQLite 数据库已保存</div>
            </div>
            <div className="metric-card">
              <div className="metric-top"><span>自动采集频率</span><span className="metric-icon orange">⟳</span></div>
              <div className="metric-value">5 <small>MINUTES</small></div>
              <div className="metric-foot"><span className="tiny-dot green" /> APScheduler 已配置</div>
            </div>
            <div className="metric-card">
              <div className="metric-top"><span>本地 AI 引擎</span><span className="metric-icon blue">✳</span></div>
              <div className="metric-value ai-value">Qwen3 <small>4B</small></div>
              <div className="metric-foot"><span className="tiny-dot green" /> Ollama · GPU 加速</div>
            </div>
          </section>

          <section className="middle-grid">
            <div className="panel chart-panel">
              <div className="panel-header">
                <div><div className="panel-title">MARKET OVERVIEW</div><div className="panel-subtitle">市场趋势与价格结构</div></div>
                <div className="preview-tag">CHART PREVIEW</div>
              </div>
              <div className="chart-live-container">
                <MarketChart />
              </div>
              <div className="chart-footer">
                <span><i className="legend-line" /> 价格走势</span>
                <span>数据来源：CoinGecko 行情快照 · SQLite</span>
              </div>
            </div>

            <div className="panel intelligence-panel">
              <div className="panel-header">
                <div><div className="panel-title">AI INTELLIGENCE</div><div className="panel-subtitle">智能分析引擎</div></div>
                <span className="ai-orb">✳</span>
              </div>
              <div className="ai-status-card">
                <div className="ai-status-top"><span className="live-dot" /> {aiOnline ? "LOCAL MODEL ONLINE" : "LOCAL MODEL OFFLINE"}</div>
                <div className="ai-model-name">Qwen3 <span>4B</span></div>
                <p>本地推理引擎已就绪，等待行情与新闻数据输入。</p>
                <div className="ai-progress"><span /></div>
                <div className="ai-progress-label"><span>ENGINE STATUS</span><b>READY</b></div>
              </div>
              <div className="intel-list">
                <div className="intel-item"><span className="intel-icon">⌁</span><div><b>Market Agent</b><small>市场数据分析模块</small></div><em>待接入</em></div>
                <div className="intel-item"><span className="intel-icon purple-text">◎</span><div><b>News Agent</b><small>新闻与社交情绪</small></div><em>待开发</em></div>
                <div className="intel-item"><span className="intel-icon orange-text">✳</span><div><b>Chief Analyst</b><small>综合研判与策略报告</small></div><em>待开发</em></div>
              </div>
            </div>
          </section>

          <section className="bottom-grid">
            <div className="panel assets-panel">
              <div className="panel-header assets-heading">
                <div><div className="panel-title">ASSET WATCHLIST</div><div className="panel-subtitle">核心资产监控列表</div></div>
                <input className="search-input" placeholder="搜索币种..." value={search} onChange={(e) => setSearch(e.target.value)} />
              </div>
              <div className="asset-table">
                <div className="table-head"><span>资产</span><span>最新价格</span><span>24H 涨跌</span><span>成交量</span><span>状态</span></div>
                {filteredCoins.map((coin) => (
                  <div className="table-row" key={coin.symbol}>
                    <div className="coin-cell"><div className={`coin-logo ${coin.symbol.toLowerCase()}`}>{coin.symbol.slice(0, 1)}</div><div><b>{coin.symbol}</b><small>{coin.name}</small></div></div>
                    <span className="muted-value">${coin.current_price == null ? "—" : Number(coin.current_price).toLocaleString("en-US", { maximumFractionDigits: 6 })}</span>
                    <span className="muted-value">{coin.price_change_percentage_24h == null ? "—" : Number(coin.price_change_percentage_24h).toFixed(2) + "%"}</span>
                    <span className="muted-value">{coin.total_volume == null ? "—" : "$" + Number(coin.total_volume).toLocaleString("en-US", { notation: "compact" })}</span>
                    <span><i className="table-status" />LIVE</span>
                  </div>
                ))}
                {filteredCoins.length === 0 && <div className="empty-state">没有找到匹配的资产</div>}
              </div>
              <div className="table-note">CoinGecko LIVE · 更新时间：{lastUpdated || "加载中..."}</div>
            </div>

            <div className="panel collection-panel">
              <div className="panel-header">
                <div><div className="panel-title">DATA COLLECTION</div><div className="panel-subtitle">自动采集任务</div></div>
                <span className="collection-icon">⟳</span>
              </div>
              <div className="collection-number">05<span> MIN</span></div>
              <div className="collection-caption">SCHEDULED COLLECTION INTERVAL</div>
              <div className="collection-line"><span /></div>
              <div className="collection-details">
                <div><span>采集引擎</span><b className="status-green">APScheduler</b></div>
                <div><span>数据来源</span><b>CoinGecko</b></div>
                <div><span>数据库</span><b>SQLite</b></div>
                <div><span>Task Status</span><b className={latestRun?.status === "success" ? "status-green" : "status-yellow"}>{latestRun?.status === "success" ? "RUNNING OK" : "WAITING"}</b></div>
              </div>
              <div className="collection-tip"><span>i</span> {latestRun ? "最近采集：" + new Date(latestRun.started_at).toLocaleString() + " · 保存：" + latestRun.saved_count + " 条" : "暂无采集记录"}</div>
            </div>
          </section>

          <footer className="footer"><span>CRYPTO RADAR AI <i>·</i> INTELLIGENCE TERMINAL</span><span>LOCAL DEVELOPMENT BUILD <b>0.1.0</b></span></footer>
        </div>
      </section>
    </main>
  );
}
