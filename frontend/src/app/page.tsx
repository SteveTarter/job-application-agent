"use client";

import React, { useState, useEffect, useRef } from "react";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  CardFooter,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert";
import {
  ResizablePanelGroup,
  ResizablePanel,
  ResizableHandle,
} from "@/components/ui/resizable";
import {
  Download,
  Paperclip,
  Send,
  Github,
  Linkedin,
  FileText,
  CheckCircle2,
  AlertCircle,
  Sparkles,
  Check,
  Loader2,
  User,
  Cpu,
  Layers,
  Activity,
  RefreshCw,
  Edit3,
  Target,
  Info,
  Briefcase,
  GraduationCap,
  Calendar,
  X,
  Mail,
  CheckSquare,
} from "lucide-react";
import {
  Radar,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
} from "recharts";

// TypeScript schemas matching app/models.py
interface ExtractedExperience {
  company: string;
  role: string;
  description: string;
}

interface ExtractedProject {
  name: string;
  description: string;
  language?: string;
}

interface ExtractedEducation {
  institution: string;
  degree: string;
  year: string;
}

interface CandidateProfile {
  name: string;
  title: string;
  experience: number;
  skills: Record<string, string[]>;
  work_experience: ExtractedExperience[];
  projects: ExtractedProject[];
  education: ExtractedEducation[];
  email: string;
  github: string;
  linkedin: string;
  confirmed: boolean;
  resume_raw: string;
}

interface JobMatch {
  company: string;
  role: string;
  score: number;
  breakdown: Record<string, number>;
  matched_skills: string[];
  missing_required: string[];
  missing_preferred: string[];
  strategy: string;
  gap_narrative: string;
  relevant_projects: string[];
}

interface AgentState {
  profile: CandidateProfile;
  current_job: JobMatch | null;
  cover_letter: string;
  draft_count: number;
  job_index: number;
}

interface ChatMessage {
  id: string;
  role: "user" | "model" | "system";
  text: string;
  isPending?: boolean;
}

export default function JobApplicationAgentDashboard() {
  const [mounted, setMounted] = useState(false);
  const [userId, setUserId] = useState("");
  const [sessionId, setSessionId] = useState("");
  const [sessionLoading, setSessionLoading] = useState(true);

  // Chat interface states
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [activeInterrupt, setActiveInterrupt] = useState<{ id: string; message: string } | null>(null);
  const [uploading, setUploading] = useState(false);

  // Workflow agent state
  const [agentState, setAgentState] = useState<AgentState>({
    profile: {
      name: "",
      title: "",
      experience: 0,
      skills: {},
      work_experience: [],
      projects: [],
      education: [],
      email: "",
      github: "",
      linkedin: "",
      confirmed: false,
      resume_raw: "",
    },
    current_job: null,
    cover_letter: "",
    draft_count: 1,
    job_index: 0,
  });

  // Track version history of cover letters locally in client state
  const [draftHistory, setDraftHistory] = useState<Record<number, string>>({});
  const [selectedDraftVersion, setSelectedDraftVersion] = useState<number>(1);

  // Right pane tab management (manually switchable once unlocked)
  const [rightPaneTab, setRightPaneTab] = useState("profile");

  const messageEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Auto scroll to bottom of chat
  useEffect(() => {
    messageEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    setMounted(true);
    initializeSession();
  }, []);

  // Initialize or restore session
  const initializeSession = async () => {
    try {
      let storedUserId = localStorage.getItem("job_agent_user_id");
      let storedSessionId = localStorage.getItem("job_agent_session_id");

      if (!storedUserId || !storedSessionId) {
        storedUserId = "user_" + Math.random().toString(36).substring(2, 11);
        localStorage.setItem("job_agent_user_id", storedUserId);

        const res = await fetch("/api/session", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ userId: storedUserId }),
        });
        const data = await res.json();
        storedSessionId = data.id;
        localStorage.setItem("job_agent_session_id", storedSessionId || "");
      }

      setUserId(storedUserId);
      setSessionId(storedSessionId || "");

      // Retrieve existing session and events
      if (storedSessionId) {
        await restoreSession(storedUserId, storedSessionId);
      }
    } catch (error) {
      console.error("Failed to initialize session", error);
      setSessionLoading(false);
    }
  };

  // Restore session state and chat history from backend
  const restoreSession = async (uid: string, sid: string) => {
    try {
      const res = await fetch(`/api/session?userId=${uid}&sessionId=${sid}`);
      if (!res.ok) throw new Error("Session not found on server");
      const sessionData = await res.json();

      // Restore agent state
      if (sessionData.state) {
        const state = sessionData.state;
        const normalizedState = {
          profile: state.profile || {},
          current_job: state.current_job || state.currentJob || null,
          cover_letter: state.cover_letter || state.coverLetter || "",
          draft_count: state.draft_count !== undefined ? state.draft_count : (state.draftCount !== undefined ? state.draftCount : 1),
          job_index: state.job_index !== undefined ? state.job_index : (state.jobIndex !== undefined ? state.jobIndex : 0),
        };
        setAgentState(normalizedState as AgentState);
        
        if (normalizedState.cover_letter) {
          setDraftHistory({ [normalizedState.draft_count]: normalizedState.cover_letter });
          setSelectedDraftVersion(normalizedState.draft_count);
          setRightPaneTab("letter");
        } else if (normalizedState.current_job) {
          setRightPaneTab("fit");
        } else if (normalizedState.profile?.name) {
          setRightPaneTab("profile");
        }
      }

      // Reconstruct message history from event list
      const events = sessionData.events || [];
      const reconstructedMessages: ChatMessage[] = [];
      let lastInterrupt: { id: string; message: string } | null = null;

      for (const ev of events) {
        const author = ev.author || ev.content?.role;
        const parts = ev.content?.parts || [];

        // Check for adk_request_input function call (interrupt)
        for (const part of parts) {
          if (part.functionCall && part.functionCall.name === "adk_request_input") {
            const args = part.functionCall.args || {};
            const interruptId = part.functionCall.id || args.interruptId;
            const message = args.message || "";
            lastInterrupt = { id: interruptId, message };
          }
        }

        // Reconstruct messages
        let text = "";
        let isUser = author === "user";

        for (const part of parts) {
          if (part.text) {
            text += part.text;
          } else if (part.functionResponse && part.functionResponse.name === "adk_request_input") {
            isUser = true;
            text += part.functionResponse.response?.result || "";
            // If this resolved the last interrupt, clear it
            if (lastInterrupt && lastInterrupt.id === part.functionResponse.id) {
              lastInterrupt = null;
            }
          }
        }

        if (text.trim()) {
          reconstructedMessages.push({
            id: ev.id || Math.random().toString(),
            role: isUser ? "user" : "model",
            text: text,
          });
        }
      }

      setMessages(reconstructedMessages);
      setActiveInterrupt(lastInterrupt);

      // If no messages exist in a new session, auto-kickoff by sending "Hi"
      if (reconstructedMessages.length === 0) {
        await startWorkflow(uid, sid);
      }
    } catch (e) {
      console.error("Failed to restore session, resetting session stores", e);
      localStorage.removeItem("job_agent_session_id");
      initializeSession();
    } finally {
      setSessionLoading(false);
    }
  };

  // Kickstart workflow with a "Hi" prompt
  const startWorkflow = async (uid: string, sid: string) => {
    setIsStreaming(true);
    const placeholderId = "placeholder-" + Date.now();
    setMessages([{ id: placeholderId, role: "model", text: "", isPending: true }]);

    try {
      const response = await fetch("/api/run_sse", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          userId: uid,
          sessionId: sid,
          newMessage: {
            role: "user",
            parts: [{ text: "Hi" }],
          },
        }),
      });

      if (!response.ok) throw new Error("Failed to connect to SSE stream");
      await readSseStream(response.body?.getReader(), placeholderId);
    } catch (error) {
      console.error(error);
      setMessages([{ id: "error", role: "system", text: "Connection failed. Please ensure the backend is running at http://127.0.0.1:8000" }]);
      setIsStreaming(false);
    }
  };

  // Read SSE chunks and update stream
  const readSseStream = async (reader: ReadableStreamDefaultReader<Uint8Array> | undefined, placeholderId: string) => {
    if (!reader) return;
    const decoder = new TextDecoder();
    let buffer = "";
    let assistantText = "";

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed) continue;

          if (trimmed.startsWith("data: ")) {
            const jsonStr = trimmed.slice(6);
            try {
              const event = JSON.parse(jsonStr);

              // 1. Check for text updates
              const parts = event.content?.parts || [];
              for (const part of parts) {
                if (part.text) {
                  assistantText += part.text;
                  setMessages((prev) =>
                    prev.map((msg) =>
                      msg.id === placeholderId
                        ? { ...msg, text: assistantText }
                        : msg
                    )
                  );
                }

                // 2. Check for input requests (interrupts)
                if (part.functionCall && part.functionCall.name === "adk_request_input") {
                  const args = part.functionCall.args || {};
                  const interruptId = part.functionCall.id || args.interruptId;
                  const message = args.message || "";
                  setActiveInterrupt({ id: interruptId, message });
                }
              }

              // 3. Check for state delta updates
              if (event.actions?.stateDelta || event.actions?.state_delta) {
                const delta = event.actions.stateDelta || event.actions.state_delta;
                setAgentState((prev) => {
                  const nextState = { ...prev };
                  
                  // Standardize fields
                  if (delta.profile) nextState.profile = { ...nextState.profile, ...delta.profile };
                  if (delta.current_job !== undefined) nextState.current_job = delta.current_job;
                  if (delta.currentJob !== undefined) nextState.current_job = delta.currentJob;
                  if (delta.cover_letter !== undefined) nextState.cover_letter = delta.cover_letter;
                  if (delta.coverLetter !== undefined) nextState.cover_letter = delta.coverLetter;
                  if (delta.draft_count !== undefined) nextState.draft_count = delta.draft_count;
                  if (delta.draftCount !== undefined) nextState.draft_count = delta.draftCount;
                  if (delta.job_index !== undefined) nextState.job_index = delta.job_index;
                  if (delta.jobIndex !== undefined) nextState.job_index = delta.jobIndex;

                  // Auto tab updates
                  if (nextState.cover_letter) {
                    setRightPaneTab("letter");
                  } else if (nextState.current_job) {
                    setRightPaneTab("fit");
                  } else if (nextState.profile?.name) {
                    setRightPaneTab("profile");
                  }

                  return nextState;
                });
              }
            } catch (err) {
              console.error("Failed to parse SSE event", trimmed, err);
            }
          }
        }
      }
    } catch (e) {
      console.error("Error reading stream", e);
    } finally {
      setIsStreaming(false);
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === placeholderId ? { ...msg, isPending: false } : msg
        )
      );

      // Save draft history on stream finish
      setAgentState((state) => {
        if (state.cover_letter) {
          setDraftHistory((history) => ({
            ...history,
            [state.draft_count]: state.cover_letter,
          }));
          setSelectedDraftVersion(state.draft_count);
        }
        return state;
      });
    }
  };

  // Download cover letter as PDF
  const handleDownloadPDF = () => {
    const text = draftHistory[selectedDraftVersion] || agentState.cover_letter;
    if (!text) return;

    try {
      const candidateName = agentState.profile?.name || "Candidate";
      const company = agentState.current_job?.company || "Company";

      const cleanName = candidateName.replace(/\s+/g, "");
      const cleanCompany = company.replace(/\s+/g, "");
      const filename = `CoverLetter-${cleanName}-${cleanCompany}.pdf`;

      // Create a hidden form to perform a standard POST navigation download,
      // avoiding client-side blob URLs which Chrome blocks on HTTP origins.
      const form = document.createElement("form");
      form.method = "POST";
      form.action = `/api/download_pdf/${filename}`;
      form.target = "_blank";
      form.style.display = "none";

      const textInput = document.createElement("input");
      textInput.type = "hidden";
      textInput.name = "text";
      textInput.value = text;
      form.appendChild(textInput);

      const nameInput = document.createElement("input");
      nameInput.type = "hidden";
      nameInput.name = "candidateName";
      nameInput.value = candidateName;
      form.appendChild(nameInput);

      const companyInput = document.createElement("input");
      companyInput.type = "hidden";
      companyInput.name = "company";
      companyInput.value = company;
      form.appendChild(companyInput);

      document.body.appendChild(form);
      form.submit();
      document.body.removeChild(form);
    } catch (err) {
      console.error("Failed to download PDF:", err);
    }
  };

  // Submit text input to agent workflow
  const handleSendMessage = async (textToSend: string) => {
    if (!textToSend.trim() || isStreaming) return;

    const userMessageText = textToSend.trim();
    setInput("");

    // Add user message to UI
    const userMsgId = "user-" + Date.now();
    setMessages((prev) => [...prev, { id: userMsgId, role: "user", text: userMessageText }]);

    // Add model placeholder
    const modelMsgId = "model-" + Date.now();
    setMessages((prev) => [...prev, { id: modelMsgId, role: "model", text: "", isPending: true }]);
    setIsStreaming(true);

    try {
      let bodyPayload: any = {
        userId,
        sessionId,
      };

      if (activeInterrupt) {
        // If answering an interrupt, send as a function response part
        bodyPayload.newMessage = {
          role: "user",
          parts: [
            {
              functionResponse: {
                id: activeInterrupt.id,
                name: "adk_request_input",
                response: {
                  result: userMessageText,
                },
              },
            },
          ],
        };
        // Clear active interrupt until backend decides next step
        setActiveInterrupt(null);
      } else {
        // Normal text message (should only happen at session start, but supporting as fallback)
        bodyPayload.newMessage = {
          role: "user",
          parts: [{ text: userMessageText }],
        };
      }

      const response = await fetch("/api/run_sse", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(bodyPayload),
      });

      if (!response.ok) throw new Error("SSE run failed");
      await readSseStream(response.body?.getReader(), modelMsgId);
    } catch (err) {
      console.error(err);
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === modelMsgId
            ? { ...msg, text: "Error sending response. Make sure the backend is active.", isPending: false }
            : msg
        )
      );
      setIsStreaming(false);
    }
  };

  // PDF File Upload Handler
  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file || uploading || isStreaming) return;

    setUploading(true);
    const uploadMsgId = "system-upload-" + Date.now();
    setMessages((prev) => [
      ...prev,
      { id: uploadMsgId, role: "system", text: `Uploading PDF resume: ${file.name}...` },
    ]);

    try {
      const formData = new FormData();
      formData.append("file", file);

      const res = await fetch("/api/upload", {
        method: "POST",
        body: formData,
      });

      if (!res.ok) throw new Error("File upload failed");
      const data = await res.json();
      const localFilePath = data.path;

      // Update system upload status
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === uploadMsgId
            ? { ...msg, text: `Successfully uploaded ${file.name}. Path saved: ${localFilePath}` }
            : msg
        )
      );

      setUploading(false);

      // Auto-submit the absolute path as the response to the resume input interrupt
      if (activeInterrupt && activeInterrupt.id.startsWith("resume_input_")) {
        await handleSendMessage(localFilePath);
      } else {
        // If not in setup interrupt, just warn the user
        setMessages((prev) => [
          ...prev,
          { id: "warn-" + Date.now(), role: "system", text: "Workflow was not active or waiting for a resume. Input path manually if needed." },
        ]);
      }
    } catch (error: any) {
      console.error(error);
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === uploadMsgId
            ? { ...msg, text: `Upload failed: ${error.message}` }
            : msg
        )
      );
      setUploading(false);
    }
  };

  // Restart the workflow and clear session keys
  const handleResetSession = () => {
    localStorage.removeItem("job_agent_session_id");
    localStorage.removeItem("job_agent_user_id");
    setUserId("");
    setSessionId("");
    setMessages([]);
    setInput("");
    setActiveInterrupt(null);
    setAgentState({
      profile: {
        name: "",
        title: "",
        experience: 0,
        skills: {},
        work_experience: [],
        projects: [],
        education: [],
        email: "",
        github: "",
        linkedin: "",
        confirmed: false,
        resume_raw: "",
      },
      current_job: null,
      cover_letter: "",
      draft_count: 1,
      job_index: 0,
    });
    setDraftHistory({});
    setRightPaneTab("profile");
    setSessionLoading(true);
    initializeSession();
  };

  // Radar Chart normalization logic
  const getRadarChartData = () => {
    if (!agentState.current_job || !agentState.current_job.breakdown) return [];
    const bd = agentState.current_job.breakdown;

    const normalized: Record<string, number> = {};
    for (const [key, val] of Object.entries(bd)) {
      normalized[key.toLowerCase()] = val as number;
    }

    const getScore = (aliases: string[]) => {
      for (const alias of aliases) {
        if (normalized[alias] !== undefined) return normalized[alias];
      }
      return 0;
    };

    return [
      { subject: "Technical", score: getScore(["technical skills", "technical"]) },
      { subject: "Experience", score: getScore(["experience level", "experience"]) },
      { subject: "Seniority", score: getScore(["seniority"]) },
      { subject: "Domain Fit", score: getScore(["domain fit", "domain"]) },
      { subject: "Culture Fit", score: getScore(["culture fit", "culture"]) },
    ];
  };

  if (!mounted) return null;

  // Compute unlocks for Right Pane navigation tabs
  const hasProfile = !!(agentState.profile?.name || agentState.profile?.title);
  const hasFitScore = !!agentState.current_job;
  const hasCoverLetter = !!agentState.cover_letter;

  return (
    <div className="flex flex-col h-screen w-screen bg-zinc-950 text-zinc-100 font-sans antialiased overflow-hidden">
      {/* Header Bar */}
      <header className="flex items-center justify-between px-6 py-4 border-b border-zinc-800 bg-zinc-900/60 backdrop-blur-md z-10">
        <div className="flex items-center space-x-3">
          <div className="p-2 bg-indigo-600/20 rounded-lg border border-indigo-500/30">
            <Cpu className="h-6 w-6 text-indigo-400 animate-pulse" />
          </div>
          <div>
            <h1 className="text-xl font-bold bg-gradient-to-r from-indigo-400 via-violet-400 to-fuchsia-400 bg-clip-text text-transparent">
              JobApplicationAgent Workspace
            </h1>
            <p className="text-xs text-zinc-400">
              Agentic profiling, fit analysis & cover letter generation
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-4">
          {sessionId && (
            <div className="hidden md:flex flex-col text-right text-[10px] text-zinc-500 leading-tight">
              <span>User: <strong className="text-zinc-400">{userId}</strong></span>
              <span>Session: <strong className="text-zinc-400">{sessionId}</strong></span>
            </div>
          )}
          <Button
            variant="outline"
            size="sm"
            onClick={handleResetSession}
            disabled={sessionLoading || isStreaming}
            className="border-zinc-700 text-zinc-300 hover:bg-zinc-800 hover:text-white transition-all text-xs"
          >
            <RefreshCw className="h-3.5 w-3.5 mr-2" />
            Reset Session
          </Button>
        </div>
      </header>

      {/* Main Workspace Pane */}
      <main className="flex-1 overflow-hidden relative">
        {sessionLoading ? (
          <div className="absolute inset-0 flex flex-col items-center justify-center bg-zinc-950/80 z-20 space-y-4">
            <Loader2 className="h-10 w-10 text-indigo-400 animate-spin" />
            <p className="text-sm text-zinc-400">Connecting to JobApplicationAgent session...</p>
          </div>
        ) : (
          <ResizablePanelGroup orientation="horizontal" className="h-full w-full">
            {/* Left Pane (Chat Interface) */}
            <ResizablePanel defaultSize={40} minSize={30} maxSize={60} className="flex flex-col border-r border-zinc-800 bg-zinc-900/10">
              {/* Message History area */}
              <div className="flex-1 overflow-hidden relative">
                <ScrollArea className="h-full px-6 py-6">
                  <div className="space-y-6 max-w-3xl mx-auto pb-4">
                    {messages.map((msg) => {
                      const isUser = msg.role === "user";
                      const isSystem = msg.role === "system";

                      if (isSystem) {
                        return (
                          <div key={msg.id} className="flex justify-center my-2">
                            <span className="px-3 py-1 text-xs bg-zinc-900 border border-zinc-800 rounded-full text-zinc-400 flex items-center space-x-1.5">
                              <Info className="h-3 w-3 text-indigo-400" />
                              <span>{msg.text}</span>
                            </span>
                          </div>
                        );
                      }

                      return (
                        <div
                          key={msg.id}
                          className={`flex ${isUser ? "justify-end" : "justify-start"} items-start space-x-3`}
                        >
                          {!isUser && (
                            <div className="h-8 w-8 rounded-lg bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center shrink-0">
                              <Cpu className="h-4.5 w-4.5 text-indigo-400" />
                            </div>
                          )}
                          <div
                            className={`max-w-[85%] rounded-xl px-4 py-3 text-sm leading-relaxed transition-all duration-300 ${
                              isUser
                                ? "bg-zinc-800 text-zinc-100 border border-zinc-700/50 shadow-md"
                                : "bg-zinc-900/60 backdrop-blur-sm border border-zinc-800 text-zinc-300 shadow-sm"
                            }`}
                          >
                            {msg.isPending && !msg.text ? (
                              <div className="flex items-center space-x-2 py-1">
                                <span className="h-2 w-2 bg-indigo-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></span>
                                <span className="h-2 w-2 bg-indigo-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></span>
                                <span className="h-2 w-2 bg-indigo-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></span>
                              </div>
                            ) : (
                              <div className="whitespace-pre-wrap select-text">{msg.text}</div>
                            )}
                          </div>
                          {isUser && (
                            <div className="h-8 w-8 rounded-lg bg-zinc-800 border border-zinc-700 flex items-center justify-center shrink-0">
                              <User className="h-4.5 w-4.5 text-zinc-400" />
                            </div>
                          )}
                        </div>
                      );
                    })}
                    <div ref={messageEndRef} />
                  </div>
                </ScrollArea>
              </div>

              {/* Interrupt Prompt Notice */}
              {activeInterrupt && (
                <div className="px-6 py-2 bg-indigo-950/20 border-t border-indigo-900/20 flex items-center justify-between">
                  <div className="flex items-center space-x-2 text-xs text-indigo-300">
                    <Sparkles className="h-3.5 w-3.5 text-indigo-400 shrink-0" />
                    <span className="font-semibold truncate">Waiting for response...</span>
                  </div>
                  <Badge variant="outline" className="bg-indigo-900/10 border-indigo-500/20 text-indigo-300 text-[10px]">
                    Interrupt ID: {activeInterrupt.id}
                  </Badge>
                </div>
              )}

              {/* Dedicated Resume PDF Upload Panel */}
              {activeInterrupt?.id.startsWith("resume_input") && (
                <div className="mx-4 my-2 p-4 rounded-xl border border-dashed border-indigo-500/30 bg-indigo-950/10 flex flex-col items-center justify-center text-center space-y-3">
                  <div className="p-2.5 bg-indigo-600/20 rounded-full border border-indigo-500/20 text-indigo-400">
                    <Paperclip className="h-5 w-5" />
                  </div>
                  <div>
                    <h4 className="text-xs font-bold text-zinc-200">Upload PDF Resume</h4>
                    <p className="text-[10px] text-zinc-400 mt-1">Select a PDF file from your device to auto-fill your profile</p>
                  </div>
                  <Button
                    type="button"
                    size="sm"
                    onClick={() => fileInputRef.current?.click()}
                    disabled={uploading || isStreaming}
                    className="bg-indigo-600 hover:bg-indigo-500 text-white text-xs h-8 px-4 font-semibold"
                  >
                    {uploading ? (
                      <>
                        <Loader2 className="h-3 w-3 animate-spin mr-1.5" />
                        Uploading...
                      </>
                    ) : (
                      "Choose PDF File"
                    )}
                  </Button>
                </div>
              )}

              {/* Chat Input form */}
              <div className="p-4 border-t border-zinc-800 bg-zinc-900/40 backdrop-blur-sm">
                <div className="relative rounded-xl border border-zinc-800 bg-zinc-950/60 focus-within:border-zinc-700 transition-all p-2">
                  <Textarea
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && !e.shiftKey) {
                        e.preventDefault();
                        handleSendMessage(input);
                      }
                    }}
                    placeholder={
                      activeInterrupt?.id.startsWith("resume_input")
                        ? "Paste resume text here, or click the clip to upload PDF..."
                        : activeInterrupt?.id.startsWith("job_input")
                        ? "Paste job posting URL or job description text..."
                        : activeInterrupt?.id.startsWith("profile_confirm")
                        ? "Type 'job postings' to proceed, or describe corrections..."
                        : activeInterrupt?.id.startsWith("letter_confirm")
                        ? "Type 'cover letter' to generate, 'update profile' to edit, or enter corrections..."
                        : activeInterrupt?.id.startsWith("refinement_input")
                        ? "Type refinement edits, 'update profile' to edit profile, or 'job postings' to analyze a new job..."
                        : "Type your message..."
                    }
                    className="w-full min-h-[50px] max-h-[200px] border-0 bg-transparent focus-visible:ring-0 focus-visible:ring-offset-0 px-2 py-2 resize-none text-sm text-zinc-100 placeholder-zinc-500"
                    rows={1}
                    disabled={isStreaming}
                  />

                  <div className="flex items-center justify-between border-t border-zinc-900 pt-2 px-1">
                    {/* File Upload Attachment Icon */}
                    <div className="flex items-center space-x-1">
                      <input
                        type="file"
                        ref={fileInputRef}
                        onChange={handleFileUpload}
                        accept=".pdf"
                        className="hidden"
                        id="resume-pdf-upload"
                      />
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        disabled={uploading || isStreaming || !activeInterrupt?.id.startsWith("resume_input")}
                        onClick={() => fileInputRef.current?.click()}
                        className="h-8 w-8 text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900 rounded-lg transition-colors"
                        title="Attach Resume PDF"
                      >
                        {uploading ? (
                          <Loader2 className="h-4 w-4 animate-spin text-indigo-400" />
                        ) : (
                          <Paperclip className="h-4 w-4" />
                        )}
                      </Button>
                      <span className="text-[10px] text-zinc-500 hidden sm:inline">
                        {activeInterrupt?.id.startsWith("resume_input") ? "Upload PDF available" : "Normal inputs only"}
                      </span>
                    </div>

                    <Button
                      onClick={() => handleSendMessage(input)}
                      disabled={!input.trim() || isStreaming}
                      size="sm"
                      className="bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg px-3 py-1 h-8 flex items-center space-x-1.5 transition-all text-xs"
                    >
                      <span>Send</span>
                      {isStreaming ? (
                        <Loader2 className="h-3 w-3 animate-spin" />
                      ) : (
                        <Send className="h-3 w-3" />
                      )}
                    </Button>
                  </div>
                </div>
              </div>
            </ResizablePanel>

            <ResizableHandle withHandle className="bg-zinc-800" />

            {/* Right Pane (Artifact Dashboard) */}
            <ResizablePanel defaultSize={60} minSize={40} maxSize={70} className="flex flex-col bg-zinc-950">
              {/* Navigation Tab list (Dynamic states check) */}
              <div className="border-b border-zinc-800 bg-zinc-900/30 px-6 py-3 flex items-center justify-between shrink-0">
                <Tabs value={rightPaneTab} onValueChange={setRightPaneTab} className="w-full">
                  <TabsList className="grid grid-cols-3 w-full max-w-[450px] bg-zinc-900 border border-zinc-800">
                    <TabsTrigger
                      value="profile"
                      disabled={!hasProfile}
                      className="text-xs text-zinc-300 hover:text-zinc-100 data-[state=active]:bg-zinc-800 data-[state=active]:text-white disabled:text-zinc-600 disabled:opacity-50 transition-all"
                    >
                      <User className="h-3.5 w-3.5 mr-1.5 shrink-0" />
                      1. Profile
                    </TabsTrigger>
                    <TabsTrigger
                      value="fit"
                      disabled={!hasFitScore}
                      className="text-xs text-zinc-300 hover:text-zinc-100 data-[state=active]:bg-zinc-800 data-[state=active]:text-white disabled:text-zinc-600 disabled:opacity-50 transition-all"
                    >
                      <Activity className="h-3.5 w-3.5 mr-1.5 shrink-0" />
                      2. Fit Score
                    </TabsTrigger>
                    <TabsTrigger
                      value="letter"
                      disabled={!hasCoverLetter}
                      className="text-xs text-zinc-300 hover:text-zinc-100 data-[state=active]:bg-zinc-800 data-[state=active]:text-white disabled:text-zinc-600 disabled:opacity-50 transition-all"
                    >
                      <FileText className="h-3.5 w-3.5 mr-1.5 shrink-0" />
                      3. Cover Letter
                    </TabsTrigger>
                  </TabsList>
                </Tabs>
              </div>

              {/* Tab Display Screens */}
              <ScrollArea className="flex-1">
                <div className="p-6 max-w-4xl mx-auto space-y-6">
                  {/* Phase 1 Dashboard: Candidate Profile */}
                  {rightPaneTab === "profile" && hasProfile && (
                    <div className="space-y-6 animate-in fade-in duration-300">
                      <Card className="border-zinc-800 bg-zinc-900/40 backdrop-blur-md shadow-xl">
                        <CardHeader className="border-b border-zinc-900 pb-4">
                          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                            <div>
                              <CardTitle className="text-2xl font-bold bg-gradient-to-r from-zinc-100 to-zinc-400 bg-clip-text text-transparent">
                                {agentState.profile.name || "Candidate Profile"}
                              </CardTitle>
                              <CardDescription className="text-zinc-400 mt-1 flex items-center">
                                <span className="font-semibold text-indigo-400 text-sm">
                                  {agentState.profile.title || "Software Engineer"}
                                </span>
                                <span className="mx-2 text-zinc-600">•</span>
                                <span className="text-xs bg-indigo-950/40 text-indigo-300 px-2.5 py-0.5 rounded-full border border-indigo-800/30">
                                  {agentState.profile.experience} years experience
                                </span>
                              </CardDescription>
                            </div>
                            
                            {/* Edit profile back-channel button */}
                            <Button
                              onClick={() => handleSendMessage("update profile")}
                              variant="outline"
                              size="sm"
                              className="self-start border-zinc-700 text-zinc-300 hover:bg-zinc-800 hover:text-white"
                              disabled={isStreaming}
                            >
                              <Edit3 className="h-3.5 w-3.5 mr-1.5" />
                              Edit Profile
                            </Button>
                          </div>

                          {/* Contact Info */}
                          <div className="flex flex-wrap gap-x-6 gap-y-2 mt-4 text-xs text-zinc-400">
                            {agentState.profile.email && (
                              <span className="flex items-center">
                                <Mail className="h-3.5 w-3.5 mr-1.5 text-zinc-500" />
                                {agentState.profile.email}
                              </span>
                            )}
                            {agentState.profile.github && (
                              <a
                                href={`https://github.com/${agentState.profile.github}`}
                                target="_blank"
                                rel="noreferrer"
                                className="flex items-center hover:text-indigo-400 transition-colors"
                              >
                                <Github className="h-3.5 w-3.5 mr-1.5 text-zinc-500" />
                                github.com/{agentState.profile.github}
                              </a>
                            )}
                            {agentState.profile.linkedin && (
                              <a
                                href={agentState.profile.linkedin}
                                target="_blank"
                                rel="noreferrer"
                                className="flex items-center hover:text-indigo-400 transition-colors"
                              >
                                <Linkedin className="h-3.5 w-3.5 mr-1.5 text-zinc-500" />
                                LinkedIn Profile
                              </a>
                            )}
                          </div>
                        </CardHeader>
                        <CardContent className="pt-6 space-y-6">
                          {/* Technical Skills grouped */}
                          <div>
                            <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-3">
                              Technical Skills
                            </h3>
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                              {Object.entries(agentState.profile.skills || {}).map(([category, skillList]) => (
                                <div
                                  key={category}
                                  className="p-3 rounded-lg bg-zinc-900/60 border border-zinc-800/80 hover:border-zinc-850 transition-all"
                                >
                                  <h4 className="text-xs font-bold text-indigo-300 mb-2 capitalize">
                                    {category}
                                  </h4>
                                  <div className="flex flex-wrap gap-1.5">
                                    {skillList.map((skill) => (
                                      <Badge
                                        key={skill}
                                        variant="secondary"
                                        className="bg-zinc-800/80 hover:bg-zinc-800 text-zinc-300 text-[11px] border border-zinc-700/20"
                                      >
                                        {skill}
                                      </Badge>
                                    ))}
                                  </div>
                                </div>
                              ))}
                            </div>
                          </div>

                          {/* Tabs structure for work exp, projects, education */}
                          <div className="pt-4 border-t border-zinc-900">
                            <Tabs defaultValue="experience" className="w-full">
                              <TabsList className="grid grid-cols-3 bg-zinc-900 border border-zinc-800 max-w-[360px] mb-4">
                                <TabsTrigger value="experience" className="text-xs text-zinc-300 hover:text-zinc-100 data-[state=active]:bg-zinc-800 data-[state=active]:text-white transition-all">
                                  <Briefcase className="h-3 w-3 mr-1" /> Experience
                                </TabsTrigger>
                                <TabsTrigger value="projects" className="text-xs text-zinc-300 hover:text-zinc-100 data-[state=active]:bg-zinc-800 data-[state=active]:text-white transition-all">
                                  <Layers className="h-3 w-3 mr-1" /> Projects
                                </TabsTrigger>
                                <TabsTrigger value="education" className="text-xs text-zinc-300 hover:text-zinc-100 data-[state=active]:bg-zinc-800 data-[state=active]:text-white transition-all">
                                  <GraduationCap className="h-3 w-3 mr-1" /> Education
                                </TabsTrigger>
                              </TabsList>

                              {/* Work Experience */}
                              <TabsContent value="experience" className="space-y-4">
                                {agentState.profile.work_experience?.length > 0 ? (
                                  agentState.profile.work_experience.map((exp, idx) => (
                                    <div
                                      key={idx}
                                      className="p-4 rounded-xl border border-zinc-900 bg-zinc-900/20"
                                    >
                                      <div className="flex justify-between items-start mb-2">
                                        <h4 className="text-sm font-bold text-zinc-100">{exp.role}</h4>
                                        <Badge variant="outline" className="text-[10px] text-zinc-400 border-zinc-800">
                                          {exp.company}
                                        </Badge>
                                      </div>
                                      <p className="text-xs text-zinc-400 whitespace-pre-wrap">{exp.description}</p>
                                    </div>
                                  ))
                                ) : (
                                  <p className="text-xs text-zinc-500 italic">No work experience entries extracted.</p>
                                )}
                              </TabsContent>

                              {/* Projects (includes GitHub repos) */}
                              <TabsContent value="projects" className="space-y-4">
                                {agentState.profile.projects?.length > 0 ? (
                                  <div className="space-y-4">
                                    {/* Github repo count status */}
                                    {agentState.profile.github && (
                                      <div className="flex items-center space-x-2 text-xs text-indigo-400 bg-indigo-950/20 px-3 py-2 rounded-lg border border-indigo-900/30">
                                        <Github className="h-4 w-4 shrink-0" />
                                        <span>
                                          Integrated {agentState.profile.projects.filter(p => p.language).length} repository summaries directly from public GitHub repos.
                                        </span>
                                      </div>
                                    )}

                                    {agentState.profile.projects.map((proj, idx) => (
                                      <div
                                        key={idx}
                                        className="p-4 rounded-xl border border-zinc-900 bg-zinc-900/20 hover:border-zinc-850 transition-all"
                                      >
                                        <div className="flex justify-between items-center mb-2">
                                          <h4 className="text-sm font-bold text-zinc-100">{proj.name}</h4>
                                          {proj.language && (
                                            <Badge className="bg-zinc-800 text-[10px] text-indigo-300">
                                              {proj.language}
                                            </Badge>
                                          )}
                                        </div>
                                        <p className="text-xs text-zinc-400">{proj.description}</p>
                                      </div>
                                    ))}
                                  </div>
                                ) : (
                                  <p className="text-xs text-zinc-500 italic">No project entries extracted.</p>
                                )}
                              </TabsContent>

                              {/* Education */}
                              <TabsContent value="education" className="space-y-4">
                                {agentState.profile.education?.length > 0 ? (
                                  agentState.profile.education.map((edu, idx) => (
                                    <div
                                      key={idx}
                                      className="p-4 rounded-xl border border-zinc-900 bg-zinc-900/20 flex items-center justify-between"
                                    >
                                      <div>
                                        <h4 className="text-sm font-bold text-zinc-100">{edu.institution}</h4>
                                        <p className="text-xs text-zinc-400 mt-1">{edu.degree}</p>
                                      </div>
                                      <Badge variant="secondary" className="bg-zinc-900 border border-zinc-800 text-xs text-zinc-400 shrink-0">
                                        <Calendar className="h-3 w-3 mr-1" />
                                        {edu.year}
                                      </Badge>
                                    </div>
                                  ))
                                ) : (
                                  <p className="text-xs text-zinc-500 italic">No education entries extracted.</p>
                                )}
                              </TabsContent>
                            </Tabs>
                          </div>
                        </CardContent>
                      </Card>
                    </div>
                  )}

                  {/* Phase 2 Dashboard: Fit Score Analysis */}
                  {rightPaneTab === "fit" && hasFitScore && agentState.current_job && (
                    <div className="space-y-6 animate-in fade-in duration-300">
                      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
                        {/* Overall score and radar chart */}
                        <div className="lg:col-span-7 space-y-6">
                          {/* Overall Match Progress */}
                          <Card className="border-zinc-800 bg-zinc-900/40 backdrop-blur-md shadow-xl">
                            <CardContent className="pt-6">
                              <div className="flex items-center justify-between mb-2">
                                <div>
                                  <span className="text-xs text-zinc-400 font-medium">OVERALL FIT MATCH</span>
                                  <h3 className="text-lg font-bold mt-0.5">{agentState.current_job.company}</h3>
                                  <p className="text-xs text-zinc-500">{agentState.current_job.role}</p>
                                </div>
                                <span className={`text-4xl font-extrabold tracking-tight ${
                                  agentState.current_job.score >= 80
                                    ? "text-emerald-400"
                                    : agentState.current_job.score >= 70
                                    ? "text-amber-400"
                                    : "text-rose-500"
                                }`}>
                                  {agentState.current_job.score}%
                                </span>
                              </div>

                              <Progress
                                value={agentState.current_job.score}
                                className="h-3.5 bg-zinc-950 rounded-full border border-zinc-800"
                              />

                              <div className="flex justify-between items-center mt-3 text-xs">
                                <Badge
                                  className={
                                    agentState.current_job.score >= 80
                                      ? "bg-emerald-950/40 text-emerald-400 border-emerald-800/30"
                                      : agentState.current_job.score >= 70
                                      ? "bg-amber-950/40 text-amber-400 border-amber-800/30"
                                      : "bg-rose-950/40 text-rose-400 border-rose-800/30"
                                  }
                                >
                                  {agentState.current_job.score >= 80 ? "Strong Match" : agentState.current_job.score >= 70 ? "Good Match" : "Reach Role"}
                                </Badge>
                                <span className="text-zinc-500">Job index #{agentState.job_index + 1}</span>
                              </div>
                            </CardContent>
                          </Card>

                          {/* Radar chart from Recharts */}
                          <Card className="border-zinc-800 bg-zinc-900/40 backdrop-blur-md shadow-xl">
                            <CardHeader className="pb-2">
                              <CardTitle className="text-sm font-bold text-zinc-300">5-Dimension Breakdown</CardTitle>
                            </CardHeader>
                            <CardContent className="h-[280px]">
                              {mounted && (
                                <ResponsiveContainer width="100%" height="100%">
                                  <RadarChart cx="50%" cy="50%" outerRadius="80%" data={getRadarChartData()}>
                                    <PolarGrid stroke="#27272a" />
                                    <PolarAngleAxis dataKey="subject" tick={{ fill: "#a1a1aa", fontSize: 10 }} />
                                    <PolarRadiusAxis angle={30} domain={[0, 100]} tick={{ fill: "#52525b", fontSize: 8 }} />
                                    <Radar
                                      name="Fit Score"
                                      dataKey="score"
                                      stroke="#6366f1"
                                      fill="#6366f1"
                                      fillOpacity={0.3}
                                    />
                                  </RadarChart>
                                </ResponsiveContainer>
                              )}
                            </CardContent>
                          </Card>
                        </div>

                        {/* Skill Lists */}
                        <div className="lg:col-span-5 space-y-6">
                          <Card className="border-zinc-800 bg-zinc-900/40 backdrop-blur-md shadow-xl h-full flex flex-col">
                            <CardHeader className="border-b border-zinc-900 pb-3">
                              <CardTitle className="text-sm font-bold text-zinc-300">Skill Alignment</CardTitle>
                            </CardHeader>
                            <CardContent className="pt-4 flex-1 space-y-4">
                              {/* Matched skills */}
                              <div>
                                <h4 className="text-xs font-semibold text-emerald-400 mb-2 flex items-center">
                                  <Check className="h-3.5 w-3.5 mr-1" />
                                  Matched Skills ({agentState.current_job.matched_skills?.length || 0})
                                </h4>
                                <div className="flex flex-wrap gap-1.5">
                                  {agentState.current_job.matched_skills?.length > 0 ? (
                                    agentState.current_job.matched_skills.map(s => (
                                      <Badge key={s} className="bg-emerald-950/20 text-emerald-400 hover:bg-emerald-950/25 border-emerald-900/30 text-[10px]">
                                        {s}
                                      </Badge>
                                    ))
                                  ) : (
                                    <span className="text-xs text-zinc-500 italic">No matching skills identified.</span>
                                  )}
                                </div>
                              </div>

                              {/* Missing Required */}
                              <div>
                                <h4 className="text-xs font-semibold text-rose-400 mb-2 flex items-center">
                                  <AlertCircle className="h-3.5 w-3.5 mr-1" />
                                  Missing Required ({agentState.current_job.missing_required?.length || 0})
                                </h4>
                                <div className="flex flex-wrap gap-1.5">
                                  {agentState.current_job.missing_required?.length > 0 ? (
                                    agentState.current_job.missing_required.map(s => (
                                      <Badge key={s} className="bg-rose-950/20 text-rose-400 hover:bg-rose-950/25 border-rose-900/30 text-[10px]">
                                        {s}
                                      </Badge>
                                    ))
                                  ) : (
                                    <span className="text-xs text-zinc-500 italic">None</span>
                                  )}
                                </div>
                              </div>

                              {/* Missing Preferred */}
                              <div>
                                <h4 className="text-xs font-semibold text-amber-400 mb-2 flex items-center">
                                  <Info className="h-3.5 w-3.5 mr-1" />
                                  Missing Preferred ({agentState.current_job.missing_preferred?.length || 0})
                                </h4>
                                <div className="flex flex-wrap gap-1.5">
                                  {agentState.current_job.missing_preferred?.length > 0 ? (
                                    agentState.current_job.missing_preferred.map(s => (
                                      <Badge key={s} className="bg-amber-950/20 text-amber-400 hover:bg-amber-950/25 border-amber-900/30 text-[10px]">
                                        {s}
                                      </Badge>
                                    ))
                                  ) : (
                                    <span className="text-xs text-zinc-500 italic">None</span>
                                  )}
                                </div>
                              </div>
                            </CardContent>
                          </Card>
                        </div>
                      </div>

                      {/* Strategy & Gap narrative in Alert */}
                      <Alert className="border-indigo-500/20 bg-gradient-to-r from-indigo-950/20 to-violet-950/15 backdrop-blur-md p-5">
                        <Sparkles className="h-5 w-5 text-indigo-400 shrink-0" />
                        <AlertTitle className="text-zinc-200 font-bold text-sm">Target Cover Letter Strategy</AlertTitle>
                        <AlertDescription className="mt-2 space-y-3">
                          <div>
                            <span className="text-xs text-zinc-400 font-semibold uppercase tracking-wider block">Strategic Angle</span>
                            <p className="text-xs text-zinc-300 mt-1 italic">"{agentState.current_job.strategy}"</p>
                          </div>
                          <div className="pt-2.5 border-t border-indigo-950/40">
                            <span className="text-xs text-zinc-400 font-semibold uppercase tracking-wider block">Gaps & Reframing Narrative</span>
                            <p className="text-xs text-zinc-300 mt-1 leading-relaxed">{agentState.current_job.gap_narrative}</p>
                          </div>
                        </AlertDescription>
                      </Alert>
                    </div>
                  )}

                  {/* Phase 3 Dashboard: Cover Letter */}
                  {rightPaneTab === "letter" && hasCoverLetter && (
                    <div className="space-y-6 animate-in fade-in duration-300">
                      {/* Draft version tabs */}
                      <div className="flex items-center justify-between">
                        <Tabs
                          value={selectedDraftVersion.toString()}
                          onValueChange={(val) => setSelectedDraftVersion(parseInt(val))}
                        >
                          <TabsList className="bg-zinc-900 border border-zinc-800">
                            {Object.keys(draftHistory).map((ver) => (
                              <TabsTrigger
                                key={ver}
                                value={ver}
                                className="text-xs px-3 text-zinc-300 hover:text-zinc-100 data-[state=active]:bg-zinc-800 data-[state=active]:text-white transition-all"
                              >
                                Draft {ver}
                              </TabsTrigger>
                            ))}
                          </TabsList>
                        </Tabs>

                        <div className="flex items-center space-x-4">
                          <span className="text-xs text-zinc-500 hidden sm:inline">
                            Total iterations: {agentState.draft_count}
                          </span>
                          <Button
                            onClick={handleDownloadPDF}
                            size="sm"
                            className="bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg px-3 py-1.5 h-8 flex items-center space-x-1.5 transition-all text-xs font-semibold"
                          >
                            <Download className="h-3.5 w-3.5" />
                            <span>Download PDF</span>
                          </Button>
                        </div>
                      </div>

                      {/* Visual Document View */}
                      <div className="rounded-xl border border-zinc-800/80 bg-zinc-900/10 shadow-xl overflow-hidden">
                        {/* Document sheet visual */}
                        <div className="p-8 bg-zinc-900/30 min-h-[300px]">
                          <div className="bg-zinc-950/80 rounded-lg border border-zinc-800 p-8 shadow-inner select-text text-zinc-300 font-serif leading-relaxed text-sm whitespace-pre-wrap max-w-[650px] mx-auto">
                            {draftHistory[selectedDraftVersion] || agentState.cover_letter}
                          </div>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Empty Dashboard State */}
                  {!hasProfile && (
                    <div className="flex flex-col items-center justify-center text-center py-20 space-y-6">
                      <div className="h-16 w-16 bg-zinc-900 border border-zinc-800 rounded-2xl flex items-center justify-center shadow-md">
                        <Sparkles className="h-8 w-8 text-indigo-400 animate-pulse" />
                      </div>
                      <div className="max-w-md">
                        <h2 className="text-lg font-bold text-zinc-200">Start JobApplicationAgent Workflow</h2>
                        <p className="text-sm text-zinc-400 mt-2 leading-relaxed">
                          Provide your resume PDF or paste your resume details in the chat to extract your candidate profile.
                        </p>
                      </div>
                    </div>
                  )}
                </div>
              </ScrollArea>
            </ResizablePanel>
          </ResizablePanelGroup>
        )}
      </main>
    </div>
  );
}
