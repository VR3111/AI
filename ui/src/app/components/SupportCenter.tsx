import { RefObject, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "./ui/accordion";
import { Button } from "./ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "./ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "./ui/dialog";
import {
  Drawer,
  DrawerContent,
  DrawerDescription,
  DrawerHeader,
  DrawerTitle,
} from "./ui/drawer";
import { Input } from "./ui/input";
import { Textarea } from "./ui/textarea";
import { useIsMobile } from "./ui/use-mobile";
import { api } from "../services/api";
import {
  decodeJwtPayload,
  getUserIdentity,
} from "../../../lib/authIdentity";
import { SupportRequestType } from "../types/api";

type SectionKey =
  | "getting-started"
  | "system-behavior"
  | "faq"
  | "contact-support";

interface SupportCenterProps {
  isOpen: boolean;
  onClose: () => void;
  currentConversationId?: string | null;
}

const faqItems = [
  {
    question: "Why didn’t my answer use a specific document?",
    answer:
      "Only indexed documents that contain enough relevant grounding are used. If a file is new, still indexing, or does not support the request, the answer may stay narrower or refuse unsupported claims.",
  },
  {
    question: "What should I do if an upload succeeds but I cannot query it yet?",
    answer:
      "Wait for indexing to complete, then retry. Large files or batches can take longer, and unindexed documents will not reliably ground responses.",
  },
  {
    question: "Can I ask broad or open-ended questions?",
    answer:
      "Yes, but the strongest results come from questions that can be tied back to the uploaded corpus. When the documents do not support an answer, the system should stay document-faithful rather than speculate.",
  },
  {
    question: "Why might the app refuse to answer?",
    answer:
      "Refusals happen when the requested claim is not supported by the indexed documents, when the request crosses policy boundaries, or when tenant isolation prevents access to the needed material.",
  },
  {
    question: "Will two users see each other’s data?",
    answer:
      "No. Conversation and document access are scoped per tenant, and responses are grounded only against the documents available in that tenant context.",
  },
];

const supportConfig: Record<
  SupportRequestType,
  {
    label: string;
    subjectPrefix: string;
    subjectPlaceholder: string;
    detailsPlaceholder: string;
    helperText: string;
    guidanceTitle: string;
    guidancePoints: string[];
  }
> = {
  issue: {
    label: "Issue report",
    subjectPrefix: "[Issue]",
    subjectPlaceholder: "Briefly summarize the bug or unexpected behavior",
    detailsPlaceholder:
      "Describe the expected behavior, actual behavior, reproduction steps, and the affected document or conversation if known.",
    helperText:
      "Use this for broken flows, incorrect results, failures, or anything that should be working but is not.",
    guidanceTitle: "Issue report checklist",
    guidancePoints: [
      "Expected behavior vs actual behavior",
      "Reproduction steps or trigger pattern",
      "Affected document, conversation, or workflow",
      "Business impact or urgency",
    ],
  },
  feature: {
    label: "Feature request",
    subjectPrefix: "[Feature Request]",
    subjectPlaceholder: "Name the capability or workflow improvement you want",
    detailsPlaceholder:
      "Describe the desired capability, the workflow problem today, who it helps, and why the change would be valuable.",
    helperText:
      "Use this when the product behaves as designed today, but an added capability would improve outcomes.",
    guidanceTitle: "Feature request checklist",
    guidancePoints: [
      "Desired capability or enhancement",
      "Current workflow pain point",
      "Who benefits and how often",
      "Business or user value if implemented",
    ],
  },
  contact: {
    label: "General contact",
    subjectPrefix: "[General Contact]",
    subjectPlaceholder: "Summarize the topic you want to discuss",
    detailsPlaceholder:
      "Share your message, question, or context. Include any relevant documents or conversation references if helpful.",
    helperText:
      "Use this for open-ended questions, account-related coordination, or support topics that do not fit the other categories.",
    guidanceTitle: "General contact checklist",
    guidancePoints: [
      "What you need or want clarified",
      "Any relevant context or timing",
      "Links to affected workflow or conversation if applicable",
      "Preferred follow-up path if special handling is needed",
    ],
  },
};

const supportSubjectPrefixes = Object.values(supportConfig).map(
  (config) => config.subjectPrefix,
);

function applySubjectPrefix(prefix: string, value: string): string {
  const trimmed = value.trim();
  if (!trimmed) {
    return `${prefix} `;
  }

  const withoutExistingPrefix = supportSubjectPrefixes.reduce(
    (subject, current) => {
      if (subject.startsWith(`${current} `)) {
        return subject.slice(current.length + 1).trim();
      }
      if (subject === current) {
        return "";
      }
      return subject;
    },
    trimmed,
  );

  return `${prefix} ${withoutExistingPrefix}`.trimEnd() + " ";
}

function SupportCenterBody({
  contactType,
  details,
  email,
  isMobile,
  isSending,
  onClose,
  onContactTypeChange,
  onCopyTemplate,
  onDetailsChange,
  onEmailChange,
  onScrollToSection,
  onSend,
  onSubjectChange,
  requestConfig,
  scrollContainerRef,
  sectionRefs,
  sendButtonText,
  subject,
  validationErrors,
}: {
  contactType: SupportRequestType;
  details: string;
  email: string;
  isMobile: boolean;
  isSending: boolean;
  onClose: () => void;
  onContactTypeChange: (value: SupportRequestType) => void;
  onCopyTemplate: () => void;
  onDetailsChange: (value: string) => void;
  onEmailChange: (value: string) => void;
  onScrollToSection: (section: SectionKey) => void;
  onSend: () => void;
  onSubjectChange: (value: string) => void;
  requestConfig: (typeof supportConfig)[SupportRequestType];
  scrollContainerRef: RefObject<HTMLDivElement | null>;
  sectionRefs: Record<SectionKey, RefObject<HTMLDivElement | null>>;
  sendButtonText: string;
  subject: string;
  validationErrors: Partial<Record<"subject" | "email" | "details", string>>;
}) {
  const cardClassName = isMobile
    ? "border-border/50 bg-card/70"
    : "border-border/40 bg-gradient-to-br from-card via-card to-card/92 shadow-[0_20px_60px_-42px_rgba(0,0,0,0.85)]";

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div
        ref={scrollContainerRef}
        className="flex-1 overflow-y-auto px-3.5 pb-[calc(env(safe-area-inset-bottom)+1rem)] sm:px-6 sm:pb-6 lg:px-8 lg:pb-8"
      >
        <div className={isMobile ? "space-y-4 sm:space-y-5" : "space-y-6"}>
          <div
            data-support-nav
            className={
              isMobile
                ? "sticky top-0 z-10 -mx-1 rounded-xl border border-border/40 bg-background/92 p-2 backdrop-blur-xl"
                : "sticky top-0 z-10 rounded-2xl border border-border/40 bg-background/85 px-3 py-3 backdrop-blur-xl"
            }
          >
            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={() => onScrollToSection("getting-started")}
                className="rounded-lg px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-secondary/70 hover:text-foreground"
              >
                Getting Started
              </button>
              <button
                type="button"
                onClick={() => onScrollToSection("system-behavior")}
                className="rounded-lg px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-secondary/70 hover:text-foreground"
              >
                System Behavior
              </button>
              <button
                type="button"
                onClick={() => onScrollToSection("faq")}
                className="rounded-lg px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-secondary/70 hover:text-foreground"
              >
                FAQ
              </button>
              <button
                type="button"
                onClick={() => onScrollToSection("contact-support")}
                className="rounded-lg px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-secondary/70 hover:text-foreground"
              >
                Contact Support
              </button>
            </div>
          </div>

          <div ref={sectionRefs["getting-started"]}>
            <Card className={cardClassName}>
              <CardHeader className={isMobile ? "pb-4" : "pb-5"}>
                <CardTitle className={isMobile ? "text-base" : "text-lg"}>
                  Getting Started
                </CardTitle>
                <CardDescription
                  className={isMobile ? "" : "max-w-3xl text-sm leading-6"}
                >
                  The fastest way to get reliable answers is to work with indexed,
                  document-backed context.
                </CardDescription>
              </CardHeader>
              <CardContent
                className={
                  isMobile
                    ? "space-y-3 text-sm text-muted-foreground"
                    : "space-y-3.5 text-sm text-muted-foreground"
                }
              >
                <div className="rounded-xl border border-border/40 bg-background/60 p-3.5">
                  <div className="mb-1 text-sm font-medium text-foreground">
                    1. Upload documents
                  </div>
                  Add PDFs, text files, or supported documents from the sidebar.
                  Upload alone does not make a file queryable.
                </div>
                <div className="rounded-xl border border-border/40 bg-background/60 p-3.5">
                  <div className="mb-1 text-sm font-medium text-foreground">
                    2. Wait for indexing
                  </div>
                  Indexed documents are the only ones the assistant can ground
                  against. If indexing is pending, answers may stay incomplete or
                  defer.
                </div>
                <div className="rounded-xl border border-border/40 bg-background/60 p-3.5">
                  <div className="mb-1 text-sm font-medium text-foreground">
                    3. Start the conversation
                  </div>
                  Ask a focused question, review the answer, then continue within
                  the same thread to refine or narrow the response.
                </div>
                <div className="rounded-xl border border-border/40 bg-background/60 p-3.5">
                  <div className="mb-1 text-sm font-medium text-foreground">
                    4. Keep usage document-grounded
                  </div>
                  Phrase requests so they can be supported by the uploaded
                  material. The product is designed to stay faithful to those
                  documents instead of inventing missing facts.
                </div>
              </CardContent>
            </Card>
          </div>

          <div ref={sectionRefs["system-behavior"]}>
            <Card className={cardClassName}>
              <CardHeader className={isMobile ? "pb-4" : "pb-5"}>
                <CardTitle className={isMobile ? "text-base" : "text-lg"}>
                  System Behavior
                </CardTitle>
                <CardDescription
                  className={isMobile ? "" : "max-w-3xl text-sm leading-6"}
                >
                  This product is optimized for grounded retrieval and predictable
                  response behavior.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-3 text-sm text-muted-foreground">
                <div className="rounded-xl border border-border/40 bg-background/60 p-3.5">
                  <div className="mb-1 text-sm font-medium text-foreground">
                    Document-faithful responses
                  </div>
                  Answers should stay anchored to indexed source material instead
                  of free-form generation.
                </div>
                <div className="rounded-xl border border-border/40 bg-background/60 p-3.5">
                  <div className="mb-1 text-sm font-medium text-foreground">
                    Possible refusals
                  </div>
                  The assistant may decline requests that are unsupported by the
                  corpus or outside allowed behavior.
                </div>
                <div className="rounded-xl border border-border/40 bg-background/60 p-3.5">
                  <div className="mb-1 text-sm font-medium text-foreground">
                    Deterministic behavior
                  </div>
                  Similar prompts over the same indexed data should produce stable
                  answer patterns, especially for well-scoped questions.
                </div>
                <div className="rounded-xl border border-border/40 bg-background/60 p-3.5">
                  <div className="mb-1 text-sm font-medium text-foreground">
                    Tenant and document isolation
                  </div>
                  Retrieval and conversations are scoped to the active tenant and
                  its accessible documents only.
                </div>
              </CardContent>
            </Card>
          </div>

          <div ref={sectionRefs.faq}>
            <Card className={cardClassName}>
              <CardHeader className={isMobile ? "pb-4" : "pb-5"}>
                <CardTitle className={isMobile ? "text-base" : "text-lg"}>
                  FAQ
                </CardTitle>
                <CardDescription
                  className={isMobile ? "" : "max-w-3xl text-sm leading-6"}
                >
                  Practical questions users hit most often during daily work.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <Accordion type="single" collapsible className="w-full">
                  {faqItems.map((item) => (
                    <AccordionItem key={item.question} value={item.question}>
                      <AccordionTrigger className="py-3 text-sm hover:no-underline">
                        {item.question}
                      </AccordionTrigger>
                      <AccordionContent className="text-sm text-muted-foreground">
                        {item.answer}
                      </AccordionContent>
                    </AccordionItem>
                  ))}
                </Accordion>
              </CardContent>
            </Card>
          </div>

          <div ref={sectionRefs["contact-support"]}>
            <Card className={cardClassName}>
              <CardHeader className={isMobile ? "pb-4" : "pb-5"}>
                <CardTitle className={isMobile ? "text-base" : "text-lg"}>
                  Contact Support
                </CardTitle>
                <CardDescription
                  className={isMobile ? "" : "max-w-3xl text-sm leading-6"}
                >
                  Capture enough context for a complete request, then send it
                  directly through the app.
                </CardDescription>
              </CardHeader>
              <CardContent className={isMobile ? "space-y-4" : "space-y-5"}>
                <div className="grid gap-3 sm:grid-cols-3">
                  <Button
                    type="button"
                    variant={contactType === "issue" ? "default" : "outline"}
                    onClick={() => onContactTypeChange("issue")}
                    className="h-11 justify-center px-4 text-center text-sm"
                  >
                    Report an Issue
                  </Button>
                  <Button
                    type="button"
                    variant={contactType === "feature" ? "default" : "outline"}
                    onClick={() => onContactTypeChange("feature")}
                    className="h-11 justify-center px-4 text-center text-sm"
                  >
                    Feature Request
                  </Button>
                  <Button
                    type="button"
                    variant={contactType === "contact" ? "default" : "outline"}
                    onClick={() => onContactTypeChange("contact")}
                    className="h-11 justify-center px-4 text-center text-sm"
                  >
                    General Contact
                  </Button>
                </div>

                <div
                  className={
                    isMobile
                      ? "rounded-xl border border-primary/20 bg-primary/5 p-4"
                      : "rounded-2xl border border-primary/20 bg-gradient-to-r from-primary/10 via-primary/5 to-transparent p-5"
                  }
                >
                  <div className="text-sm font-medium text-foreground">
                    {requestConfig.label}
                  </div>
                  <p className="mt-1.5 text-sm leading-6 text-muted-foreground">
                    {requestConfig.helperText}
                  </p>
                </div>

                <div className={isMobile ? "space-y-3" : "space-y-4 pt-1"}>
                  <div className="space-y-2">
                    <label className="text-sm font-medium text-foreground">
                      Subject
                    </label>
                    <Input
                      value={subject}
                      onChange={(event) => onSubjectChange(event.target.value)}
                      placeholder={requestConfig.subjectPlaceholder}
                      aria-invalid={!!validationErrors.subject}
                      className={isMobile ? "" : "h-10"}
                    />
                    {validationErrors.subject && (
                      <p className="text-xs text-destructive">
                        {validationErrors.subject}
                      </p>
                    )}
                  </div>

                  <div className="space-y-2">
                    <label className="text-sm font-medium text-foreground">
                      Contact email
                    </label>
                    <Input
                      type="email"
                      value={email}
                      onChange={(event) => onEmailChange(event.target.value)}
                      placeholder="name@company.com"
                      aria-invalid={!!validationErrors.email}
                      className={isMobile ? "" : "h-10"}
                    />
                    {validationErrors.email && (
                      <p className="text-xs text-destructive">
                        {validationErrors.email}
                      </p>
                    )}
                  </div>

                  <div className="space-y-2">
                    <label className="text-sm font-medium text-foreground">
                      Details
                    </label>
                    <Textarea
                      value={details}
                      onChange={(event) => onDetailsChange(event.target.value)}
                      placeholder={requestConfig.detailsPlaceholder}
                      className={isMobile ? "min-h-32" : "min-h-52"}
                      aria-invalid={!!validationErrors.details}
                    />
                    {validationErrors.details && (
                      <p className="text-xs text-destructive">
                        {validationErrors.details}
                      </p>
                    )}
                  </div>
                </div>

                <div
                  className={
                    isMobile
                      ? "rounded-xl border border-border/40 bg-background/60 p-4"
                      : "rounded-2xl border border-border/40 bg-background/60 p-5"
                  }
                >
                  <div className="mb-3 text-sm font-medium text-foreground">
                    {requestConfig.guidanceTitle}
                  </div>
                  <ul className="space-y-2.5 text-sm leading-6 text-muted-foreground">
                    {requestConfig.guidancePoints.map((point) => (
                      <li key={point} className="flex items-start gap-2.5">
                        <span className="mt-2 h-1.5 w-1.5 rounded-full bg-primary/80" />
                        <span>{point}</span>
                      </li>
                    ))}
                  </ul>
                </div>

                <div
                  className={
                    isMobile
                      ? "sticky bottom-0 -mx-1 flex flex-col gap-2 rounded-xl border border-border/40 bg-background/92 p-3 backdrop-blur-xl"
                      : "rounded-2xl border border-border/40 bg-background/40 px-5 py-4"
                  }
                >
                  <p className="text-xs leading-5 text-muted-foreground">
                    Send is the primary path. Copy remains available as a fallback
                    if delivery fails or you need to share the request manually.
                  </p>
                  <div
                    className={
                      isMobile
                        ? "flex flex-col gap-2 sm:flex-row"
                        : "mt-4 flex flex-wrap items-center justify-end gap-3 pt-1"
                    }
                  >
                    <Button type="button" variant="outline" onClick={onClose}>
                      Close
                    </Button>
                    <Button type="button" variant="outline" onClick={onCopyTemplate}>
                      Copy Support Draft
                    </Button>
                    <Button type="button" onClick={onSend} disabled={isSending}>
                      {sendButtonText}
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
}

export function SupportCenter({
  isOpen,
  onClose,
  currentConversationId,
}: SupportCenterProps) {
  const isMobile = useIsMobile();
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const sectionRefs: Record<SectionKey, RefObject<HTMLDivElement | null>> = {
    "getting-started": useRef<HTMLDivElement>(null),
    "system-behavior": useRef<HTMLDivElement>(null),
    faq: useRef<HTMLDivElement>(null),
    "contact-support": useRef<HTMLDivElement>(null),
  };
  const [contactType, setContactType] = useState<SupportRequestType>("issue");
  const [subject, setSubject] = useState(
    `${supportConfig.issue.subjectPrefix} `,
  );
  const [email, setEmail] = useState("");
  const [details, setDetails] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [validationErrors, setValidationErrors] = useState<
    Partial<Record<"subject" | "email" | "details", string>>
  >({});

  const requestConfig = supportConfig[contactType];

  const requestTypeLabel = useMemo(() => {
    switch (contactType) {
      case "feature":
        return "Feature request";
      case "contact":
        return "General contact";
      default:
        return "Issue report";
    }
  }, [contactType]);

  useEffect(() => {
    if (!isOpen) return;

    const { email: fallbackEmail } = getUserIdentity(
      api.getAuthHeader(),
      api.getIdentity(),
    );
    if (!email && fallbackEmail !== "unknown@local") {
      setEmail(fallbackEmail);
    }
  }, [email, isOpen]);

  const handleOpenChange = (open: boolean) => {
    if (!open) {
      onClose();
    }
  };

  const handleContactTypeChange = (value: SupportRequestType) => {
    setContactType(value);
    setSubject((current) =>
      applySubjectPrefix(supportConfig[value].subjectPrefix, current),
    );
    setValidationErrors({});
  };

  const handleScrollToSection = (section: SectionKey) => {
    const container = scrollContainerRef.current;
    const target = sectionRefs[section].current;

    if (!container || !target) return;

    const containerRect = container.getBoundingClientRect();
    const targetRect = target.getBoundingClientRect();
    const stickyNav = container.querySelector("[data-support-nav]");
    const stickyNavHeight =
      stickyNav instanceof HTMLElement ? stickyNav.offsetHeight : 0;
    const top =
      targetRect.top -
      containerRect.top +
      container.scrollTop -
      stickyNavHeight -
      16;

    container.scrollTo({
      top,
      behavior: "smooth",
    });
  };

  const validate = () => {
    const nextErrors: Partial<Record<"subject" | "email" | "details", string>> =
      {};

    const normalizedSubject = subject.trim();
    const normalizedEmail = email.trim();
    const normalizedDetails = details.trim();

    if (!normalizedSubject || supportSubjectPrefixes.includes(normalizedSubject)) {
      nextErrors.subject = "Enter a subject for this request.";
    }
    if (!normalizedEmail) {
      nextErrors.email = "Enter a contact email.";
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(normalizedEmail)) {
      nextErrors.email = "Enter a valid email address.";
    }
    if (!normalizedDetails) {
      nextErrors.details = "Enter request details.";
    }

    setValidationErrors(nextErrors);
    return Object.keys(nextErrors).length === 0;
  };

  const handleCopyTemplate = async () => {
    const authHeader = api.getAuthHeader();
    const rawToken = authHeader?.startsWith("Bearer ")
      ? authHeader.replace("Bearer ", "").trim()
      : authHeader ?? "";
    const payload = rawToken ? decodeJwtPayload(rawToken) : null;
    const conversationId = currentConversationId ?? api.getCurrentConversationId();
    const tenantId =
      (payload && typeof payload.tenant_id === "string"
        ? payload.tenant_id
        : null) ??
      api.getIdentity()?.tenant_id ??
      "Unknown";
    const draft = [
      `Support request type: ${requestTypeLabel}`,
      `Subject: ${subject || "[add subject]"}`,
      `Contact email: ${email || "[add email]"}`,
      `Tenant: ${tenantId}`,
      `Conversation ID: ${conversationId || "N/A"}`,
      `Timestamp: ${new Date().toISOString()}`,
      `Destination: vkrl3111@gmail.com`,
      "",
      "Details:",
      details ||
        "[describe the request, affected document/conversation, expected behavior, and actual behavior]",
    ].join("\n");

    try {
      await navigator.clipboard.writeText(draft);
      toast.success("Support draft copied to clipboard");
    } catch (error) {
      toast.error("Failed to copy support draft");
    }
  };

  const handleSend = async () => {
    if (!validate()) {
      return;
    }

    const conversationId = currentConversationId ?? api.getCurrentConversationId();
    const normalizedSubject = subject.trim();
    const normalizedEmail = email.trim();
    const normalizedDetails = details.trim();

    setIsSending(true);
    try {
      await api.submitSupportRequest({
        request_type: contactType,
        subject: normalizedSubject,
        contact_email: normalizedEmail,
        details: normalizedDetails,
        conversation_id: conversationId,
        client_timestamp: new Date().toISOString(),
      });

      toast.success("Support request sent to vkrl3111@gmail.com");
      setDetails("");
      setValidationErrors({});
      setSubject(`${requestConfig.subjectPrefix} `);
      onClose();
    } catch (error) {
      console.error("SUPPORT_REQUEST_SEND_FAILED", error);
      toast.error("Failed to send support request");
    } finally {
      setIsSending(false);
    }
  };

  const content = (
    <SupportCenterBody
      contactType={contactType}
      details={details}
      email={email}
      isMobile={isMobile}
      isSending={isSending}
      onClose={onClose}
      onContactTypeChange={handleContactTypeChange}
      onCopyTemplate={handleCopyTemplate}
      onDetailsChange={setDetails}
      onEmailChange={setEmail}
      onScrollToSection={handleScrollToSection}
      onSend={handleSend}
      onSubjectChange={setSubject}
      requestConfig={requestConfig}
      scrollContainerRef={scrollContainerRef}
      sectionRefs={sectionRefs}
      sendButtonText={isSending ? "Sending..." : "Send Support Request"}
      subject={subject}
      validationErrors={validationErrors}
    />
  );

  if (isMobile) {
    return (
      <Drawer open={isOpen} onOpenChange={handleOpenChange}>
        <DrawerContent className="max-h-[94vh] rounded-t-2xl">
          <DrawerHeader className="border-b border-border/50 px-4 pt-3 pb-3.5">
            <div className="flex items-start justify-between gap-4">
              <div>
                <DrawerTitle className="text-base">Support Center</DrawerTitle>
                <DrawerDescription className="mt-0.5 text-[11px] leading-5">
                  Product guidance, behavior details, and support intake in one
                  place.
                </DrawerDescription>
              </div>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                onClick={onClose}
                aria-label="Close support center"
              >
                <svg
                  className="size-4"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M6 18L18 6M6 6l12 12"
                  />
                </svg>
              </Button>
            </div>
          </DrawerHeader>
          {content}
        </DrawerContent>
      </Drawer>
    );
  }

  return (
    <Dialog open={isOpen} onOpenChange={handleOpenChange}>
      <DialogContent className="flex max-h-[92vh] max-w-[min(1180px,calc(100vw-2.5rem))] flex-col gap-0 overflow-hidden rounded-2xl border-border/50 bg-gradient-to-b from-background via-background to-card/80 p-0 shadow-[0_40px_120px_-48px_rgba(0,0,0,0.95)] duration-300">
        <DialogHeader className="border-b border-border/50 bg-gradient-to-r from-card/95 via-card/80 to-card/60 px-7 py-6 text-left">
          <DialogTitle className="text-xl">Support Center</DialogTitle>
          <DialogDescription>
            Product guidance, behavior details, and support intake in one
            place.
          </DialogDescription>
        </DialogHeader>
        {content}
      </DialogContent>
    </Dialog>
  );
}
