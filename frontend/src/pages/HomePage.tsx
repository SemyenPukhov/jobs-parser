import { usePendingJobs, usePostponedJobs, useAcceptOrRejectJob } from "@/api/useJobs";
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { formatDate, daysAgo } from "@/lib/utils";
import { Dismiss28Regular, Checkmark28Regular, Pause28Regular } from "@fluentui/react-icons";
import { useState } from "react";
import { Textarea } from "@/components/ui/textarea";
import DialogWrapper from "../components/DialogWrapper";

const ACCEPT_TEXTS = {
  title: "Сделали подачу",
  description: "Кого подали?",
  action: "accept",
  commentRequired: true,
};

const REJECT_TEXT = {
  title: "Не будем подаваться",
  description: "Почему не будем?",
  action: "reject",
  commentRequired: true,
};

const POSTPONE_TEXT = {
  title: "Отложить вакансию",
  description: "Комментарий (опционально)",
  action: "postpone",
  commentRequired: false,
};

type AllowedActions = "accept" | "reject" | "postpone";
export default function HomePage() {
  const [dialogConfig, setDialogConfig] = useState<null | typeof ACCEPT_TEXTS>(null);
  const [comment, setComment] = useState("");
  const [source, setSource] = useState("");
  const [activeTab, setActiveTab] = useState("pending");

  const [id, setId] = useState<string | null>(null);

  const { data: jobsResponse, isLoading } = usePendingJobs(source);
  const { data: postponedResponse, isLoading: isLoadingPostponed } = usePostponedJobs(source);
  const { mutate: acceptOrRejectJob } = useAcceptOrRejectJob();
  
  const sources =
    jobsResponse && jobsResponse.available_sources
      ? jobsResponse.available_sources
      : [];

  const jobs =
    jobsResponse && jobsResponse.jobs && jobsResponse.jobs.length > 0
      ? jobsResponse.jobs
      : [];

  const postponedJobs =
    postponedResponse && postponedResponse.jobs && postponedResponse.jobs.length > 0
      ? postponedResponse.jobs
      : [];

  const open = Boolean(dialogConfig);
  const handleOpenChange = (action?: AllowedActions, jobId?: string) => {
    if (!dialogConfig && action && jobId) {
      if (action === "accept") {
        setDialogConfig(ACCEPT_TEXTS);
      } else if (action === "reject") {
        setDialogConfig(REJECT_TEXT);
      } else if (action === "postpone") {
        setDialogConfig(POSTPONE_TEXT);
      }
      setId(jobId);
    } else if (dialogConfig) {
      setDialogConfig(null);
      setComment("");
    }
  };

  const onSubmit = () => {
    if (!dialogConfig || !id) {
      return;
    }

    acceptOrRejectJob({ 
      id, 
      action: dialogConfig.action as AllowedActions, 
      comment: comment || undefined 
    });
    setDialogConfig(null);
    setComment("");
  };
  const renderJobCard = (j: any, showPostponeButton: boolean = true) => {
    const daysAgoText =
      daysAgo(j.parsed_at) > 0
        ? `${daysAgo(j.parsed_at)} дня назад`
        : "Сегодня";
    return (
      <Card key={j.id}>
        <CardHeader>
          <CardTitle>
            <div className="flex">
              <span className="flex gap-2 mr-auto items-center">
                {j.source}
                {j.amocrm_lead_id && (
                  <a
                    href={`https://fortech.amocrm.ru/leads/detail/${j.amocrm_lead_id}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium rounded-full bg-blue-100 text-blue-800 hover:bg-blue-200 transition-colors"
                    title="Открыть в AmoCRM"
                  >
                    🏢 В CRM
                  </a>
                )}
              </span>
              <a href={j.company_url} target="_blank">
                Компания:{" "}
                <span className="font-bold">{j.company}</span>
              </a>
            </div>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col gap-2">
            <div className="flex justify-between gap-2">
              <h3 className="font-bold">{j.title}</h3>
              <a href={j.url} target="_blank">
                Ссылка на вакансию
              </a>
            </div>

            <div>
              <Accordion type="single" collapsible className="w-full" defaultValue={j.matching_results ? "matching" : undefined}>
                {j.matching_results && (
                  <AccordionItem value="matching">
                    <AccordionTrigger>
                      <div className="flex items-center gap-2">
                        <span>Кого надо подать 🎯</span>
                        {j.matching_results.matched_at && (
                          <span className="text-xs text-muted-foreground font-normal">
                            (сматчено: {formatDate(j.matching_results.matched_at)})
                          </span>
                        )}
                      </div>
                    </AccordionTrigger>
                    <AccordionContent className="flex flex-col gap-3">
                      {j.matching_results.matches && j.matching_results.matches.length > 0 ? (
                        j.matching_results.matches.map((match: any) => (
                          <div key={match.developer_id} className="border rounded-lg p-4 space-y-2">
                            <div className="flex items-center justify-between">
                              <h4 className="font-semibold text-lg">{match.developer_name}</h4>
                              <span className="text-sm font-medium px-3 py-1 rounded-full bg-primary/10">
                                {match.score}%
                              </span>
                            </div>
                            
                            <div className="space-y-1">
                              <div className="flex justify-between text-xs text-muted-foreground">
                                <span>Совпадение</span>
                                <span>{match.score}%</span>
                              </div>
                              <Progress 
                                value={match.score} 
                                className={`h-2 ${
                                  match.score >= 80 ? '[&>*]:bg-green-500' : 
                                  match.score >= 60 ? '[&>*]:bg-yellow-500' : 
                                  '[&>*]:bg-orange-500'
                                }`}
                              />
                            </div>

                            <Accordion type="single" collapsible className="w-full">
                              <AccordionItem value="reasoning" className="border-0">
                                <AccordionTrigger className="text-sm py-2">
                                  Обоснование
                                </AccordionTrigger>
                                <AccordionContent className="text-sm text-muted-foreground">
                                  {match.reasoning}
                                </AccordionContent>
                              </AccordionItem>
                            </Accordion>
                          </div>
                        ))
                      ) : (
                        <p className="text-muted-foreground text-center py-4">Матчей нет</p>
                      )}
                    </AccordionContent>
                  </AccordionItem>
                )}
                
                <AccordionItem value="item-1">
                  <AccordionTrigger>
                    Описание запроса
                  </AccordionTrigger>
                  <AccordionContent className="flex flex-col gap-4 text-balance text-left">
                    {j.description
                      .split("\n")
                      .filter(Boolean)
                      .map((text: any, i: any) => (
                        <p key={i}>{text}</p>
                      ))}
                  </AccordionContent>
                </AccordionItem>
              </Accordion>
            </div>
          </div>
        </CardContent>

        <CardFooter>
          <CardAction>
            <div className="flex gap-3">
              <Button
                size="icon"
                onClick={() => handleOpenChange("reject", j.id)}
                title="Отклонить"
              >
                <Dismiss28Regular className="text-red-500" />
              </Button>

              {showPostponeButton && (
                <Button
                  size="icon"
                  onClick={() => handleOpenChange("postpone", j.id)}
                  title="Отложить"
                >
                  <Pause28Regular className="text-yellow-500" />
                </Button>
              )}

              <Button
                size="icon"
                onClick={() => handleOpenChange("accept", j.id)}
                title="Подать"
              >
                <Checkmark28Regular className="text-green-500" />
              </Button>
            </div>
          </CardAction>
          <CardDescription className="flex gap-2 ml-auto">
            Спарсили: {formatDate(j.parsed_at)} ({daysAgoText})
          </CardDescription>
        </CardFooter>
      </Card>
    );
  };

  return (
    <>
      <DialogWrapper
        title={dialogConfig?.title as string}
        open={open}
        description={dialogConfig?.description}
        onOpenChange={() => handleOpenChange()}
      >
        <Textarea
          value={comment}
          placeholder={dialogConfig?.commentRequired ? "Ответ на вопрос выше" : "Комментарий (опционально)"}
          onChange={(e) => setComment(e.target.value)}
        />
        <Button 
          onClick={onSubmit} 
          variant="ghost" 
          disabled={dialogConfig?.commentRequired && !comment}
        >
          Отправить
        </Button>
      </DialogWrapper>

      <div className="flex flex-col p-[16px] pt-0">
        <div className="flex items-center h-[48px] mb-4">
          <div className="ml-auto">
            <Select onValueChange={(v) => setSource(v)}>
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder="Ресурс" />
              </SelectTrigger>
              <SelectContent>
                {sources.map((s: string) => {
                  return (
                    <SelectItem key={s} value={s}>
                      {s}
                    </SelectItem>
                  );
                })}
              </SelectContent>
            </Select>
          </div>
        </div>

        <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
          <TabsList className="grid w-full grid-cols-2 mb-4">
            <TabsTrigger value="pending">
              Необработанные ({jobs.length})
            </TabsTrigger>
            <TabsTrigger value="postponed">
              Отложенные ({postponedJobs.length})
            </TabsTrigger>
          </TabsList>

          <TabsContent value="pending">
            <div className="flex flex-col gap-2 text-center">
              {isLoading && (
                <h2 className="scroll-m-20 border-b pb-2 text-3xl font-semibold tracking-tight first:mt-0">
                  Загрузка вакансий
                </h2>
              )}
              {!isLoading && jobs.length === 0 && (
                <h2 className="scroll-m-20 border-b pb-2 text-3xl font-semibold tracking-tight first:mt-0">
                  Новых нет. Все обработаны 💯
                </h2>
              )}
              {!isLoading && jobs.length > 0 && jobs.map((j: any) => renderJobCard(j, true))}
            </div>
          </TabsContent>

          <TabsContent value="postponed">
            <div className="flex flex-col gap-2 text-center">
              {isLoadingPostponed && (
                <h2 className="scroll-m-20 border-b pb-2 text-3xl font-semibold tracking-tight first:mt-0">
                  Загрузка отложенных вакансий
                </h2>
              )}
              {!isLoadingPostponed && postponedJobs.length === 0 && (
                <h2 className="scroll-m-20 border-b pb-2 text-3xl font-semibold tracking-tight first:mt-0">
                  Отложенных вакансий нет ⏸️
                </h2>
              )}
              {!isLoadingPostponed && postponedJobs.length > 0 && postponedJobs.map((j: any) => renderJobCard(j, false))}
            </div>
          </TabsContent>
        </Tabs>
      </div>
    </>
  );
}
