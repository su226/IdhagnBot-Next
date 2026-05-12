import { Box, Stack } from "@mui/material";
import { type ReactNode } from "react";

export default function EmptyContainer({ children }: { children: ReactNode }) {
  return (
    <Box sx={{
      minHeight: "100vh",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      flexDirection: "column",
      padding: 2,
      textAlign: "center",
    }}>
      <Stack spacing={2} sx={{ maxWidth: "100%" }}>
        {children}
      </Stack>
    </Box>
  );
}