import { Alert, Box, Checkbox, FormControlLabel, Grid, LinearProgress, Paper, Skeleton, SvgIcon, TextField, Typography, type SvgIconProps } from "@mui/material";
import DashboardContainer from "../components/DashboardContainer";
import { useMemo, useState, type FC } from "react";
import z from "zod";
import { useQuery } from "@tanstack/react-query";
import { Result } from "../utils/response";
import { AccessTime, Extension, Memory, Message } from "@mui/icons-material";

const OverviewBase = z.object({
  name: z.string(),
  icon: z.nullable(z.string()),
  type: z.string(),
});

const OverviewString = OverviewBase.extend({
  type: z.literal("string"),
  value: z.string(),
});

const OverviewNumber = OverviewBase.extend({
  type: z.literal("number"),
  value: z.number(),
  unit: z.nullable(z.string()),
});

const OverviewRatio = OverviewBase.extend({
  type: z.literal("ratio"),
  value: z.number(),
  max: z.number(),
  unit: z.nullable(z.string()),
});

const OverviewItem = z.union([OverviewString, OverviewNumber, OverviewRatio]);

const OverviewData = z.object({
  items: z.record(z.string(), OverviewItem),
});

type OverviewItem = z.infer<typeof OverviewItem>;

function round1(num: number): string {
  if (Number.isInteger(num)) {
    return num.toString();
  }
  return num.toFixed(1);
}

function createIcon(path: string): FC<SvgIconProps> {
  function Icon(props: SvgIconProps) {
    return <SvgIcon {...props}><path d={path} /></SvgIcon>;
  }
  return Icon;
}

const ICONS: Record<string, FC<SvgIconProps>> = {
  chip: Memory,
  chip2: createIcon("M6,4H18V5H21V7H18V9H21V11H18V13H21V15H18V17H21V19H18V20H6V19H3V17H6V15H3V13H6V11H3V9H6V7H3V5H6V4M11,15V18H12V15H11M13,15V18H14V15H13M15,15V18H16V15H15Z"),
  bot: createIcon("M12,2A2,2 0 0,1 14,4C14,4.74 13.6,5.39 13,5.73V7H14A7,7 0 0,1 21,14H22A1,1 0 0,1 23,15V18A1,1 0 0,1 22,19H21V20A2,2 0 0,1 19,22H5A2,2 0 0,1 3,20V19H2A1,1 0 0,1 1,18V15A1,1 0 0,1 2,14H3A7,7 0 0,1 10,7H11V5.73C10.4,5.39 10,4.74 10,4A2,2 0 0,1 12,2M7.5,13A2.5,2.5 0 0,0 5,15.5A2.5,2.5 0 0,0 7.5,18A2.5,2.5 0 0,0 10,15.5A2.5,2.5 0 0,0 7.5,13M16.5,13A2.5,2.5 0 0,0 14,15.5A2.5,2.5 0 0,0 16.5,18A2.5,2.5 0 0,0 19,15.5A2.5,2.5 0 0,0 16.5,13Z"),
  plugin: Extension,
  python: createIcon("M19.14,7.5A2.86,2.86 0 0,1 22,10.36V14.14A2.86,2.86 0 0,1 19.14,17H12C12,17.39 12.32,17.96 12.71,17.96H17V19.64A2.86,2.86 0 0,1 14.14,22.5H9.86A2.86,2.86 0 0,1 7,19.64V15.89C7,14.31 8.28,13.04 9.86,13.04H15.11C16.69,13.04 17.96,11.76 17.96,10.18V7.5H19.14M14.86,19.29C14.46,19.29 14.14,19.59 14.14,20.18C14.14,20.77 14.46,20.89 14.86,20.89A0.71,0.71 0 0,0 15.57,20.18C15.57,19.59 15.25,19.29 14.86,19.29M4.86,17.5C3.28,17.5 2,16.22 2,14.64V10.86C2,9.28 3.28,8 4.86,8H12C12,7.61 11.68,7.04 11.29,7.04H7V5.36C7,3.78 8.28,2.5 9.86,2.5H14.14C15.72,2.5 17,3.78 17,5.36V9.11C17,10.69 15.72,11.96 14.14,11.96H8.89C7.31,11.96 6.04,13.24 6.04,14.82V17.5H4.86M9.14,5.71C9.54,5.71 9.86,5.41 9.86,4.82C9.86,4.23 9.54,4.11 9.14,4.11C8.75,4.11 8.43,4.23 8.43,4.82C8.43,5.41 8.75,5.71 9.14,5.71Z"),
  time: AccessTime,
  message: Message,
};

function Item({ id, item }: { id: string, item: OverviewItem }) {
  let content;
  if (item.type === "string") {
    content = <Typography>{item.value}</Typography>;
  } else if (item.type === "number") {
    let value;
    if (item.unit === "s") {
      let hour, minute, second;
      second = item.value;
      minute = Math.floor(second / 60);
      second = Math.floor(second % 60);
      hour = Math.floor(minute / 60);
      minute = minute % 60;
      const day = Math.floor(hour / 24);
      hour = hour % 24;
      value = `${day}d ${hour.toString().padStart(2, "0")}:${minute.toString().padStart(2, "0")}:${second.toString().padStart(2, "0")}`;
    } else {
      value = round1(item.value);
    }
    content = <Typography>{value}</Typography>;
  } else if (item.type === "ratio") {
    let value = round1(item.value);
    if (item.unit === "%" && item.max === 100) {
      value += "%";
    } else {
      value += "/" + round1(item.max) + item.unit;
    }
    content = (
      <>
        <Typography>{value}</Typography>
        <LinearProgress
          variant="determinate"
          value={item.value / item.max * 100}
          sx={{ mt: 0.5 }}
        />
      </>
    );
  } else {
    content = <Typography>不支持的数据</Typography>;
  }
  const Icon = item.icon && ICONS[item.icon];
  return (
    <Paper variant="outlined" sx={{ p: 2, height: "100%", position: "relative" }}>
      {Icon &&
        <Icon
          sx={theme => ({
            position: "absolute",
            top: theme.spacing(1.5),
            right: theme.spacing(1.5),
            opacity: 0.1,
            fontSize: 48,
          })}
        />
      }
      <Typography variant="h5" component="h2">
        {item.name}
      </Typography>
      <Typography variant="caption" sx={{ opacity: 0.5, wordBreak: "break-all" }}>{id}</Typography>
      {content}
    </Paper>
  );
}

export default function Dashboard() {
  const [autoRefresh, setAutoRefresh] = useState(true);
  const query = useQuery({
    queryKey: ["dashboard"],
    queryFn: async () => {
      const response = await fetch("/idhagnbot-api/dashboard", {
        headers: {
          Authorization: `Bearer ${sessionStorage.token}`,
        },
      });
      const result = Result.parse(await response.json());
      if (!result.success) {
        throw Error(result.message);
      }
      return OverviewData.parse(result.data);
    },
    refetchInterval: autoRefresh ? 10000 : false,
  });
  const [filter, setFilter] = useState("");
  const filtered = useMemo(() => {
    const items = query.data?.items;
    if (!items) {
      return [];
    }
    const entries = Object.entries(items);
    if (filter) {
      return entries.filter(([id, item]) => 
        id.indexOf(filter) !== -1 || item.name.indexOf(filter) !== -1
      );
    }
    return entries;
  }, [filter, query.data]);

  let items;
  if (query.isLoading) {
    items = (
      <Grid container spacing={2} sx={{ m: 2, mt: 0 }}>
        {Array.from({ length: 16 }, (_, i) =>
          <Grid key={i} size={{ xs: 6, sm: 4, lg: 3 }}>
            <Skeleton variant="rectangular" height={120} />
          </Grid>
        )}
      </Grid>
    );
  } else if (filtered.length === 0) {
    items = (
      <Box sx={{
        flexGrow: 1,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        p: 2,
        pt: 0,
        textAlign: "center",
      }}>
        {filter ? "没有符合条件的项目" : "没有插件提供仪表盘项目"}
      </Box>
    );
  } else {
    items = (
      <Grid container spacing={2} sx={{ m: 2, mt: 0 }}>
        {filtered.map(([id, item]) =>
          <Grid key={id} size={{ xs: 6, sm: 4, lg: 3 }}>
            <Item id={id} item={item} />
          </Grid>
        )}
      </Grid>
    );
  }

  return (
    <DashboardContainer>
      <Box sx={{ position: "relative" }}>
        {query.isFetching &&
          <LinearProgress sx={{ position: "absolute", top: 0, left: 0, width: "100%" }} />
        }
        <Box sx={{ m: 2, display: "flex", gap: 2 }}>
          <TextField
            label="过滤"
            value={filter}
            onChange={event => setFilter(event.target.value)}
            sx={{ flex: 1 }}
          />
          <FormControlLabel
            control={
              <Checkbox
                checked={autoRefresh}
                onChange={event => setAutoRefresh(event.target.checked)}
              />
            }
            label="自动刷新"
            sx={{ mr: 0 }}
          />
        </Box>
        {query.error &&
          <Alert severity="error" sx={{ m: 2, mt: 0 }}>{query.error.toString()}</Alert>
        }
        {items}
      </Box>
    </DashboardContainer>
  );
}
