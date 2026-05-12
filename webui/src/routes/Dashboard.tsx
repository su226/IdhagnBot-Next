import { Box } from "@mui/material";
import DashboardContainer from "../components/DashboardContainer";

export default function Dashboard() {
  return (
    <DashboardContainer>
      <Box sx={{
        flexGrow: 1,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: 2,
        textAlign: "center",
      }}>
        这里空空如也
        <br />
        敬请期待 IdhagnBot 未来的更新
      </Box>
    </DashboardContainer>
  );
}
