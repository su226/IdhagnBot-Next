import {
  AppBar,
  Box,
  Button,
  Divider,
  Drawer,
  IconButton,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  styled,
  Toolbar,
  Tooltip,
  Typography,
  useMediaQuery,
  useTheme,
  type CSSObject,
  type SxProps,
  type Theme,
} from "@mui/material";
import { ChevronLeft, Dashboard, Logout, Menu, Settings } from "@mui/icons-material";
import { useState, type ReactNode } from "react";
import { Link, useLocation, useNavigate } from "react-router";
import type { SystemStyleObject } from "@mui/system";

const drawerWidth = 250;

const openedMixin = (theme: Theme): CSSObject => ({
  width: drawerWidth,
  transition: theme.transitions.create("width", {
    easing: theme.transitions.easing.sharp,
    duration: theme.transitions.duration.enteringScreen,
  }),
  overflowX: "hidden",
});

const closedMixin = (theme: Theme): CSSObject => ({
  width: `calc(${theme.spacing(8)} + 1px)`,
  transition: theme.transitions.create("width", {
    easing: theme.transitions.easing.sharp,
    duration: theme.transitions.duration.leavingScreen,
  }),
  overflowX: "hidden",
});

const DesktopDrawer = styled(Drawer, { shouldForwardProp: prop => prop !== "open" })(
  ({ theme }) => ({
    width: drawerWidth,
    flexShrink: 0,
    whiteSpace: "nowrap",
    boxSizing: "border-box",
    variants: [
      {
        props: ({ open }) => open,
        style: {
          ...openedMixin(theme),
          "& .MuiDrawer-paper": openedMixin(theme),
        },
      },
      {
        props: ({ open }) => !open,
        style: {
          ...closedMixin(theme),
          "& .MuiDrawer-paper": closedMixin(theme),
        },
      },
    ],
  }),
);

const PrimarySpan = styled("span")(({ theme }) => ({
  color: theme.palette.primary.main,
}));

function DrawerItem(props: {
  icon: ReactNode,
  text?: string,
  to?: string,
  desktop?: boolean,
  open?: boolean
}) {
  const desktop = props.desktop ?? false;
  const open = props.open ?? true;
  const icon = props.icon;
  const text = props.text ?? "";
  const to = props.to ?? "/";
  const location = useLocation();
  const selected = location.pathname === to;

  const item = (
    <ListItem disablePadding>
      <ListItemButton component={Link} sx={{ px: desktop ? 2.5 : 2 }} to={to} selected={selected}>
        <ListItemIcon>{icon}</ListItemIcon>
        <ListItemText primary={text} sx={{ opacity: open ? 1 : 0 }} />
      </ListItemButton>
    </ListItem>
  );

  return open ? item : <Tooltip title={text} placement="right">{item}</Tooltip>;
}

function DrawerList(props: { desktop?: boolean, open?: boolean }) {
  const desktop = props.desktop ?? false;
  const open = props.open ?? true;

  return (
    <List>
      <DrawerItem icon={<Dashboard />} text="仪表盘" to="/dashboard" desktop={desktop} open={open} />
      <DrawerItem icon={<Settings />} text="配置编辑器" to="/config" desktop={desktop} open={open} />
    </List>
  );
}

function DesktopLogoutButton(props: { open?: boolean }) {
  const open = props.open ?? false;
  const navigate = useNavigate();

  const logout = () => {
    delete localStorage.token;
    navigate("/");
  };

  return (
    <Box sx={theme => ({
      position: "sticky",
      bottom: 0,
      backgroundColor: theme.palette.background.default
    })}>
      <Divider />
      <Toolbar disableGutters>
        {
          open
            ?
            <Button
              variant="outlined"
              color="error"
              onClick={logout}
              sx={{ mx: 1.5, width: "100%" }}
            >
              登出
            </Button>
            :
            <Tooltip title="登出" placement="right" sx={{ ml: 1.5 }}>
              <IconButton onClick={logout}>
                <Logout />
              </IconButton>
            </Tooltip>
        }
      </Toolbar>
    </Box>
  );
}

function expand_sx<T extends object>(sx?: SxProps<T>): ReadonlyArray<boolean | SystemStyleObject<T> | ((theme: T) => SystemStyleObject<T>)> {
  if (sx === null || sx === undefined) {
    return [];
  } else if (sx instanceof Array) {
    return sx;
  } else {
    return [sx];
  }
}

export default function DashboardContainer(props: { children?: ReactNode, sx?: SxProps<Theme> }) {
  const theme = useTheme();
  const desktop = useMediaQuery(theme.breakpoints.up("md"));
  const [mobileOpen, setMobileOpen] = useState(false);
  const [desktopOpen, setDesktopOpenRaw] = useState(localStorage.desktopMenuOpen === "true");
  const navigate = useNavigate();

  const setDesktopOpen = (open: boolean) => {
    setDesktopOpenRaw(open);
    localStorage.desktopMenuOpen = open;
  }

  const logout = () => {
    delete localStorage.token;
    navigate("/");
  };

  return (
    desktop
      ?
      <Box sx={{ display: "flex" }}>
        <DesktopDrawer variant="permanent" open={desktopOpen}>
          <Box sx={theme => ({
            position: "sticky",
            top: 0,
            zIndex: 1,
            backgroundColor: theme.palette.background.default
          })}>
            <Toolbar>
              {desktopOpen &&
                <Typography variant="h6" component="div">
                  <PrimarySpan>Idhagn</PrimarySpan>
                  Bot
                </Typography>
              }
              <IconButton
                onClick={() => setDesktopOpen(!desktopOpen)}
                sx={{ position: "absolute", top: 12, right: 12 }}
              >
                {desktopOpen ? <ChevronLeft /> : <Menu />}
              </IconButton>
            </Toolbar>
            <Divider />
          </Box>
          <DrawerList desktop open={desktopOpen} />
          <Box sx={{ flexGrow: 1 }} />
          <DesktopLogoutButton open={desktopOpen} />
        </DesktopDrawer>
        <Box sx={[
          {
            display: "flex",
            minWidth: 0, // 允许内容收缩
            minHeight: "100vh",
            flex: 1,
            flexDirection: "column",
          },
          ...expand_sx(props.sx)
        ]}>
          {props.children}
        </Box>
      </Box>
      :
      <Box sx={[
        { display: "flex", minHeight: "100vh", flexDirection: "column" },
        ...expand_sx(props.sx)
      ]}>
        <Drawer
          variant="temporary"
          open={mobileOpen}
          onClose={() => setMobileOpen(false)}
          sx={{ "& .MuiPaper-root": { minWidth: drawerWidth } }}
        >
          <DrawerList />
        </Drawer>
        <AppBar position="fixed" color="default">
          <Toolbar>
            <IconButton color="inherit" edge="start" onClick={() => setMobileOpen(true)}>
              <Menu />
            </IconButton>
            <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
              <PrimarySpan>Idhagn</PrimarySpan>
              Bot
            </Typography>
            <Tooltip title="登出">
              <IconButton color="inherit" edge="end" onClick={logout}>
                <Logout />
              </IconButton>
            </Tooltip>
          </Toolbar>
        </AppBar>
        <Toolbar />
        {props.children}
      </Box>
  );
}
