import z from "zod";

export const Result = z.object({
  code: z.string(),
  message: z.string(),
  data: z.unknown(),
});

export type Result = z.infer<typeof Result>;

export const CODE_SUCCESS = "success";
