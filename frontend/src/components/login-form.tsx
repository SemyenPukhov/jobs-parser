import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";

const formSchema = z.object({
  email: z.string().email({ message: "Не похоже на email" }),
  password: z.string({ message: "Нужно заполнить" }).min(3, "Нужно длиннее"),
});

interface LoginFormProps extends React.ComponentProps<"div"> {
  onLogin: (values: z.infer<typeof formSchema>) => void;
  loading?: boolean;
}

export function LoginForm({
  className,
  onLogin,
  loading,
  ...props
}: LoginFormProps) {
  const form = useForm<z.infer<typeof formSchema>>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      email: "",
    },
  });

  return (
    <div
      className={cn("flex flex-col gap-6 min-w-[380px]", className)}
      {...props}
    >
      <Form {...form}>
        <form
          onSubmit={form.handleSubmit(onLogin)}
          className="space-y-8 w-full"
        >
          <Card>
            <CardHeader>
              <CardTitle>Вход ☀️</CardTitle>
              <CardDescription>Нужна почта и пароль</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex flex-col gap-6">
                <div className="grid gap-3">
                  <FormField
                    control={form.control}
                    name="email"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Почта</FormLabel>
                        <FormControl>
                          <Input
                            id="email"
                            placeholder="m@example.com"
                            {...field}
                          />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>
                <div className="grid gap-3">
                  <FormField
                    control={form.control}
                    name="password"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Пароль</FormLabel>
                        <FormControl>
                          <Input id="password" type="password" {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>
                <div className="flex flex-col gap-3">
                  <Button
                    type="submit"
                    className="w-full bg-[#0a0a0a]!"
                    disabled={loading}
                  >
                    {loading ? "Пробую" : "Войти"}
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        </form>
      </Form>
    </div>
  );
}
