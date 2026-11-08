"use client";

import { FormEvent, ReactNode, useEffect, useState } from "react";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";
const TOKEN_KEY = "crypto-radar-session";

type User = { id: number; username: string; role: string; created_at: string };

export default function AuthGate({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [mode, setMode] = useState<"login" | "register">("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    const token = window.sessionStorage.getItem(TOKEN_KEY);
    if (!token) {
      setLoading(false);
      return;
    }
    fetch(API_BASE_URL + "/api/auth/me", {
      headers: { Authorization: "Bearer " + token },
      cache: "no-store",
    })
      .then(async (response) => {
        if (!response.ok) throw new Error("登录状态已过期");
        const payload = await response.json();
        setUser(payload.user);
      })
      .catch(() => window.sessionStorage.removeItem(TOKEN_KEY))
      .finally(() => setLoading(false));
  }, []);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    if (mode === "register" && password !== confirmPassword) {
      setError("两次输入的密码不一致");
      return;
    }
    setSubmitting(true);
    try {
      const endpoint = mode === "login" ? "/api/auth/login" : "/api/auth/register";
      const response = await fetch(API_BASE_URL + endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: username.trim(), password }),
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload.detail || "请求失败，请稍后重试");

      if (mode === "register") {
        setMode("login");
        setPassword("");
        setConfirmPassword("");
        setError("注册成功，请使用新账号登录。");
        return;
      }

      window.sessionStorage.setItem(TOKEN_KEY, payload.access_token);
      setUser(payload.user);
      setPassword("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "登录失败");
    } finally {
      setSubmitting(false);
    }
  }

  function logout() {
    window.sessionStorage.removeItem(TOKEN_KEY);
    setUser(null);
    setPassword("");
    setMode("login");
  }

  if (loading) {
    return <div className="auth-loading"><span className="auth-spinner" />正在验证安全会话…</div>;
  }

  if (user) {
    return (
      <>
        <div className="auth-session-bar">
          <div className="auth-session-user">
            <span className="auth-session-avatar">{user.username.slice(0, 2).toUpperCase()}</span>
            <span>{user.username}</span>
            <b className={user.role === "svip" ? "svip-pill" : "member-pill"}>
              {user.role === "svip" ? "✦ SVIP" : user.role.toUpperCase()}
            </b>
          </div>
          <button onClick={logout}>退出登录 ↗</button>
        </div>
        {children}
      </>
    );
  }

  return (
    <main className="auth-screen">
      <div className="auth-grid-glow" />
      <section className="auth-card">
        <div className="auth-brand">
          <div className="auth-brand-mark">R<span /></div>
          <div><b>CRYPTO<span>RADAR</span></b><small>AI INTELLIGENCE TERMINAL</small></div>
        </div>
        <div className="auth-eyebrow"><i /> SECURE MEMBER ACCESS</div>
        <h1>{mode === "login" ? "欢迎回来" : "创建账户"}</h1>
        <p className="auth-subtitle">
          {mode === "login" ? "登录以进入你的加密市场智能终端。" : "注册 Crypto Radar AI 账号，开启市场监控。"}
        </p>

        <div className="auth-mode-switch">
          <button className={mode === "login" ? "active" : ""} onClick={() => { setMode("login"); setError(""); }}>登录</button>
          <button className={mode === "register" ? "active" : ""} onClick={() => { setMode("register"); setError(""); }}>注册</button>
        </div>

        <form className="auth-form" onSubmit={submit}>
          <label htmlFor="auth-username">用户名</label>
          <input id="auth-username" value={username} onChange={(e) => setUsername(e.target.value)} placeholder="请输入用户名" autoComplete="username" minLength={3} maxLength={24} required />
          <label htmlFor="auth-password">密码</label>
          <input id="auth-password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="至少 10 位，区分大小写" autoComplete={mode === "login" ? "current-password" : "new-password"} minLength={10} required />
          {mode === "register" && (
            <>
              <label htmlFor="auth-confirm">确认密码</label>
              <input id="auth-confirm" type="password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} placeholder="再次输入密码" autoComplete="new-password" minLength={10} required />
            </>
          )}
          {error && <div className={error.includes("注册成功") ? "auth-notice" : "auth-error"}>{error}</div>}
          <button className="auth-submit" type="submit" disabled={submitting}>
            {submitting ? "请稍候…" : mode === "login" ? "进入终端  ↗" : "创建账户  ↗"}
          </button>
        </form>

        <div className="auth-security"><span>◈</span> 密码采用 PBKDF2 安全哈希存储 · 会话有效期 7 天</div>
        <div className="auth-footer">CRYPTO RADAR AI <i>·</i> MARKET INTELLIGENCE</div>
      </section>
      <div className="auth-side-note"><span>01 / ACCESS CONTROL</span><b>DATA-DRIVEN.<br />AI-POWERED.</b><p>实时行情 · 本地 AI 推理 · 智能市场研究</p></div>
    </main>
  );
}
