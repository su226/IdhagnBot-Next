import z from "zod";

export const Result = z.object({
  success: z.boolean(),
  message: z.string(),
  data: z.unknown(),
});

export type Result = z.infer<typeof Result>;
