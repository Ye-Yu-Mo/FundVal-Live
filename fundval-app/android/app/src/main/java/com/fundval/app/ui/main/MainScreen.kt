package com.fundval.app.ui.main

import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material.icons.outlined.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import com.fundval.app.navigation.Destination
import com.fundval.app.ui.auth.LoginScreen
import com.fundval.app.ui.auth.RegisterScreen
import com.fundval.app.ui.main.MainTab

data class MainTab(
    val label: String,
    val route: String,
    val selectedIcon: ImageVector,
    val unselectedIcon: ImageVector
)

val mainTabs = listOf(
    MainTab("自选", Destination.Watchlist.route, Icons.Filled.Star, Icons.Outlined.Star),
    MainTab("基金", Destination.Funds.route, Icons.Filled.TrendingUp, Icons.Outlined.TrendingUp),
    MainTab("持仓", Destination.Positions.route, Icons.Filled.AccountBalance, Icons.Outlined.AccountBalance),
    MainTab("账户", Destination.Accounts.route, Icons.Filled.Folder, Icons.Outlined.Folder),
    MainTab("我的", Destination.Profile.route, Icons.Filled.Person, Icons.Outlined.Person)
)

@Composable
fun MainScreen(
    onLogout: () -> Unit
) {
    val innerNavController = rememberNavController()

    Scaffold(
        bottomBar = {
            NavigationBar {
                val navBackStackEntry by innerNavController.currentBackStackEntryAsState()
                val currentRoute = navBackStackEntry?.destination?.route

                mainTabs.forEach { tab ->
                    NavigationBarItem(
                        selected = currentRoute == tab.route,
                        onClick = {
                            if (currentRoute != tab.route) {
                                innerNavController.navigate(tab.route) {
                                    popUpTo(Destination.Watchlist.route) {
                                        saveState = true
                                    }
                                    launchSingleTop = true
                                    restoreState = true
                                }
                            }
                        },
                        icon = {
                            Icon(
                                imageVector = if (currentRoute == tab.route) {
                                    tab.selectedIcon
                                } else {
                                    tab.unselectedIcon
                                },
                                contentDescription = tab.label
                            )
                        },
                        label = { Text(tab.label) }
                    )
                }
            }
        }
    ) { innerPadding ->
        NavHost(
            navController = innerNavController,
            startDestination = Destination.Watchlist.route,
            modifier = Modifier.padding(innerPadding)
        ) {
            composable(Destination.Watchlist.route) {
                PlaceholderScreen("自选列表\n即将上线")
            }
            composable(Destination.Funds.route) {
                PlaceholderScreen("基金浏览\n即将上线")
            }
            composable(Destination.Positions.route) {
                PlaceholderScreen("持仓管理\n即将上线")
            }
            composable(Destination.Accounts.route) {
                PlaceholderScreen("账户管理\n即将上线")
            }
            composable(Destination.Profile.route) {
                PlaceholderScreen("个人中心\n即将上线")
            }
        }
    }
}
