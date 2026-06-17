"use client"
import { useState, useRef, useEffect } from "react"
import { useMutation } from "@tanstack/react-query"
import { useAuth } from "@/components/auth/auth-provider"
import { sendMessage, type ChatResponse } from "@/lib/api/chat"
import { PageHeader } from "@/components/shared/page-header"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { EmptyState } from "@/components/shared/empty-state"
import { Loader2, Send, User, Bot, AlertTriangle } from "lucide-react"

interface Msg { role: "user"|"assistant"; content: string; escalated?: boolean }

export default function CoachPage() {
  const { user } = useAuth()
  const [msgs, setMsgs] = useState<Msg[]>([])
  const [input, setInput] = useState("")
  const [cid, setCid] = useState<string|null>(null)
  const ref = useRef<HTMLDivElement>(null)
  const cm = useMutation({ mutationFn: (m: string) => sendMessage(m, cid || undefined), onSuccess: (d: ChatResponse) => { if (!cid) setCid(d.conv_id); setMsgs(p => [...p, { role: "assistant", content: d.response, escalated: d.escalated }]) } })
  useEffect(() => { ref.current?.scrollIntoView({ behavior: "smooth" }) }, [msgs])
  const send = () => { const m = input.trim(); if (!m || cm.isPending) return; setMsgs(p => [...p, { role: "user", content: m }]); setInput(""); cm.mutate(m) }

  return <div className="flex flex-col gap-4 p-4 md:p-6 h-[calc(100vh-8rem)]">
    <PageHeader title="AI Coach" description="Ask fitness questions and get personalized advice" />
    <Card className="flex-1 flex flex-col overflow-hidden"><CardContent className="flex-1 overflow-y-auto p-4 space-y-4">
      {msgs.length === 0 && <EmptyState icon={Bot} title="Ask Your Coach" description="Ask about exercises, training tips, or get form advice" />}
      {msgs.map((m, i) => <div key={i} className={`flex gap-3 ${m.role === "user" ? "justify-end" : ""}`}>{m.role === "assistant" && <Bot className="size-6 mt-1 text-lime-600 shrink-0" />}<div className={`rounded-lg px-4 py-2 max-w-[80%] text-sm ${m.role === "user" ? "bg-lime-500 text-white" : "bg-muted"}`}>{m.escalated && <div className="flex items-center gap-1 text-amber-600 text-xs mb-1 font-medium"><AlertTriangle className="size-3" />Safety Notice</div>}<p className="whitespace-pre-wrap">{m.content}</p></div>{m.role === "user" && <User className="size-6 mt-1 text-muted-foreground shrink-0" />}</div>)}
      {cm.isPending && <div className="flex gap-3"><Bot className="size-6 mt-1 text-lime-600" /><div className="bg-muted rounded-lg px-4 py-2"><Loader2 className="animate-spin size-4" /></div></div>}
      <div ref={ref} />
    </CardContent><div className="border-t p-4 flex gap-2"><Input value={input} onChange={e => setInput(e.target.value)} onKeyDown={e => e.key === "Enter" && send()} placeholder="Ask a fitness question..." disabled={cm.isPending} /><Button onClick={send} disabled={cm.isPending || !input.trim()}><Send className="size-4" /></Button></div></Card>
  </div>
}
