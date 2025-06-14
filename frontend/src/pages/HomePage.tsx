import { usePendingJobs, useAcceptOrRejectJob } from "@/api/useJobs";
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
import { formatDate, daysAgo } from "@/lib/utils";
import { Dismiss28Regular, Checkmark28Regular } from "@fluentui/react-icons";
import { useState } from "react";
import { Textarea } from "@/components/ui/textarea";
import DialogWrapper from "../components/DialogWrapper";

const ACCEPT_TEXTS = {
  title: "Сделали подачу",
  description: "Кого подали?",
  action: "accept",
};

const REJECT_TEXT = {
  title: "Не будем подаваться",
  description: "Почему не будем?",
  action: "reject",
};

type AllowedActions = "accept" | "reject";
export default function HomePage() {
  const [title, setTitle] = useState<null | typeof ACCEPT_TEXTS>(null);
  const [comment, setComment] = useState("");
  const [source, setSource] = useState("");

  const [id, setId] = useState<string | null>(null);

  const { data: jobsResponse, isLoading } = usePendingJobs(source);
  const { mutate: acceptOrRejectJob } = useAcceptOrRejectJob();
  const sources =
    jobsResponse && jobsResponse.available_sources
      ? jobsResponse.available_sources
      : [];

  const open = Boolean(title);
  const handleOpenChange = (action?: AllowedActions, id?: string) => {
    if (!title && action && id) {
      setTitle(action === "accept" ? ACCEPT_TEXTS : REJECT_TEXT);
      setId(id);
    } else if (title) {
      setTitle(null);
      setComment("");
    }
  };

  const onSubmit = () => {
    if (!title || !id) {
      return;
    }

    acceptOrRejectJob({ id, action: title.action as AllowedActions, comment });
    setTitle(null);
    setComment("");
  };
  return (
    <>
      <DialogWrapper
        title={title?.title as string}
        open={open}
        description={title?.description}
        onOpenChange={() => handleOpenChange()}
      >
        <Textarea
          value={comment}
          placeholder="Ответ на вопрос выше"
          onChange={(e) => setComment(e.target.value)}
        />
        <Button onClick={onSubmit} variant="ghost" disabled={!comment}>
          Отправить
        </Button>
      </DialogWrapper>

      <div className="flex flex-col">
        {!isLoading && sources.length > 0 && (
          <div className="flex items-center h-[48px]">
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
        )}
        <div className="flex flex-col gap-2">
          {isLoading && (
            <h2 className="scroll-m-20 border-b pb-2 text-3xl font-semibold tracking-tight first:mt-0">
              Загрузка вакансий
            </h2>
          )}
          {!isLoading &&
            jobsResponse &&
            jobsResponse.jobs &&
            jobsResponse.jobs.length == 0 && (
              <h2 className="scroll-m-20 border-b pb-2 text-3xl font-semibold tracking-tight first:mt-0">
                Новых нет. Все обработаны 💯
              </h2>
            )}
          {!isLoading &&
            jobsResponse.jobs?.map((j: any) => {
              const daysAgoText =
                daysAgo(j.parsed_at) > 0
                  ? `${daysAgo(j.parsed_at)} дня назад`
                  : "Сегодня";
              return (
                <Card key={j.id}>
                  <CardHeader>
                    <CardTitle>
                      <div className="flex">
                        <span className="flex gap-2 mr-auto">{j.source}</span>
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
                        <Accordion type="single" collapsible className="w-full">
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
                        >
                          <Dismiss28Regular className=" text-red-500" />
                        </Button>

                        <Button
                          size="icon"
                          onClick={() => handleOpenChange("accept", j.id)}
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
            })}
        </div>
      </div>
    </>
  );
}
