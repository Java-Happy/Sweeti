"use client";

import { FormEvent, useEffect, useRef, useState } from "react";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";

type Brief = {
  generated_at: string;
  model: string;
  content: string;
  source_snapshot_at?: string | null;
};

type Message = { role: "user" | "assistant"; content: string };

export default function AIWorkspace() {
  const [tab, setTab] = useState<"brief" | "chat">("brief");
  const [brief, setBrief] = useState<Brief | null>(null);
  const [briefError, setBriefError] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [lastChecked, setLastChecked] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let active = true;
    const loadBrief = async () => {
      try {
        const response = await fetch(API_BASE_URL + "/api/ai/brief", { cache: "no-store" });
        if (!response.ok) throw new Error("简报服务暂不可用");
        const payload = await response.json();
        if (active) {
          setBrief(payload.brief || null);
          setBriefError("");
          setLastChecked(new Date().toLocaleTimeString("zh-CN"));
        }
      } catch (error) {
        if (active) setBriefError(error instanceof Error ? error.message : "读取简报失败");
      }
    };
    loadBrief();
    const timer = window.setInterval(loadBrief, 30000);
    return () => { active = false; window.clearInterval(timer); };
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, sending]);

  async function sendMessage(event: FormEvent) {
    event.preventDefault();
    const question = input.trim();
    if (!question || sending) return;
    const nextMessages: Message[] = [...messages, { role: "user", content: question }];
    setMessages(nextMessages);
    setInput("");
    setSending(true);
    try {
      const response = await fetch(API_BASE_URL + "/api/ai/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: question,
          conversation: messages.slice(-4)
        })
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.detail || "Qwen3 请求失败");
      }
      if (!response.body) throw new Error("浏览器不支持流式响应");

      // 先插入空的助手消息，再逐块更新，形成实时打字效果。
      const assistantMessages: Message[] = [...nextMessages, { role: "assistant", content: "" }];
      setMessages(assistantMessages);
      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let answer = "";
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        answer += decoder.decode(value, { stream: true });
        setMessages([...nextMessages, { role: "assistant", content: answer }]);
      }
      answer += decoder.decode();
      setMessages([...nextMessages, { role: "assistant", content: answer || "模型没有返回内容。" }]);
    } catch (error) {
      setMessages([...nextMessages, {
        role: "assistant",
        content: error instanceof Error ? "请求失败：" + error.message : "请求失败，请检查后端和 Ollama。"
      }]);
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="ai-workspace">
      <div className="ai-tabs">
        <button className={tab === "brief" ? "active" : ""} onClick={() => setTab("brief")}>MARKET BRIEF</button>
        <button className={tab === "chat" ? "active" : ""} onClick={() => setTab("chat")}>ASK QWEN3</button>
      </div>

      {tab === "brief" ? (
        <div className="brief-view">
          <div className="brief-meta">
            <span><i className="live-dot" /> AUTO REFRESH · 5 MIN</span>
            <span>{brief?.generated_at ? new Date(brief.generated_at).toLocaleString("zh-CN") : "等待首次生成"}</span>
          </div>
          {brief ? (
            <div className="brief-content">{brief.content}</div>
          ) : (
            <div className="brief-empty">
              <div className="brief-loader">✳</div>
              <b>Qwen3 市场简报准备中</b>
              <p>简报将在后端完成下一轮行情采集后自动生成。此处每 30 秒检查一次更新。</p>
              {briefError && <small>{briefError}</small>}
            </div>
          )}
          <div className="brief-foot">MODEL · QWEN3 4B　/　SOURCE · COINGECKO + SQLITE　/　检查 · {lastChecked || "—"}</div>
        </div>
      ) : (
        <div className="chat-view">
          <div className="chat-messages">
            {messages.length === 0 && (
              <div className="chat-welcome">
                <span className="chat-spark">✳</span>
                <b>和 Qwen3 开始对话</b>
                <p>我会参考本地保存的最新行情快照。你可以问市场趋势、币种表现或风险。</p>
                <div className="chat-suggestions">
                  {["BTC 和 ETH 当前表现如何？", "最近涨幅靠前的币有哪些？", "当前市场主要风险是什么？"].map((item) => (
                    <button key={item} onClick={() => setInput(item)}>{item}</button>
                  ))}
                </div>
              </div>
            )}
            {messages.map((message, index) => (
              <div className={"chat-message " + message.role} key={index}>
                <span>{message.role === "user" ? "YOU" : "QWEN3"}</span>
                <p>{message.content}</p>
              </div>
            ))}
            {sending && <div className="chat-thinking"><i /> Qwen3 正在生成 · 流式输出中</div>}
            <div ref={messagesEndRef} />
          </div>
          <form className="chat-form" onSubmit={sendMessage}>
            <input value={input} onChange={(event) => setInput(event.target.value)} placeholder="向 Qwen3 提问，例如：BTC 当前走势如何？" maxLength={4000} />
            <button type="submit" disabled={!input.trim() || sending}>{sending ? "分析中" : "发送 ↗"}</button>
          </form>
          <div className="chat-disclaimer">LIVE STREAM · TOP 30 MARKET CONTEXT · 回答基于本地行情快照及模型推理，仅供研究参考。</div>
        </div>
      )}
    </div>
  );
}
