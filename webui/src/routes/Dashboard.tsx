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
  type Theme,
} from "@mui/material";
import {
  ChevronLeft,
  Dashboard as DashboardIcon,
  Logout,
  Menu,
  Settings
} from "@mui/icons-material";
import { useEffect, useState, type ReactNode } from "react";
import { Link, Outlet, useLocation, useNavigate } from "react-router";

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
      <DrawerItem
        icon={<DashboardIcon />}
        text="仪表盘"
        to="/dashboard"
        desktop={desktop}
        open={open}
      />
      <DrawerItem
        icon={<Settings />}
        text="配置编辑器"
        to="/dashboard/config"
        desktop={desktop}
        open={open}
      />
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

export default function Dashboard() {
  const theme = useTheme();
  const desktop = useMediaQuery(theme.breakpoints.up("md"));
  const [mobileOpen, setMobileOpen] = useState(false);
  const [desktopOpen, setDesktopOpenRaw] = useState(localStorage.desktopMenuOpen === "true");
  const navigate = useNavigate();
  const location = useLocation();

  const setDesktopOpen = (open: boolean) => {
    setDesktopOpenRaw(open);
    localStorage.desktopMenuOpen = open;
  }

  const logout = () => {
    delete sessionStorage.token;
    delete localStorage.token;
    navigate("/");
  };

  useEffect(() => {
    if (!sessionStorage.token) {
      navigate("/", { state: { back: location } });
    }
  }, []);

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
        <Box sx={{
          display: "flex",
          minWidth: 0, // 允许内容收缩
          height: "100vh",
          flex: 1,
          flexDirection: "column",
        }}>
          <Outlet />
        </Box>
      </Box>
      :
      <Box sx={{ display: "flex", height: "100vh", flexDirection: "column" }}>
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
        <Outlet />
      </Box>
  );
}
