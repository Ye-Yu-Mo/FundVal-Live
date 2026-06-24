package com.fundval.app.navigation

import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import com.fundval.app.ui.auth.LoginScreen
import com.fundval.app.ui.auth.LoginViewModel
import com.fundval.app.ui.auth.RegisterScreen
import com.fundval.app.ui.funds.CompareScreen
import com.fundval.app.ui.funds.FundDetailScreen
import com.fundval.app.ui.main.MainScreen

@Composable
fun AppNavGraph(
    isLoggedIn: Boolean
) {
    val navController = rememberNavController()

    val startDestination = if (isLoggedIn) {
        Destination.Main.route
    } else {
        Destination.Login.route
    }

    NavHost(
        navController = navController,
        startDestination = startDestination
    ) {
        composable(Destination.Login.route) {
            LoginScreen(
                onLoginSuccess = {
                    navController.navigate(Destination.Main.route) {
                        popUpTo(Destination.Login.route) { inclusive = true }
                    }
                },
                onNavigateToRegister = {
                    navController.navigate(Destination.Register.route)
                }
            )
        }

        composable(Destination.Register.route) {
            RegisterScreen(
                onRegisterSuccess = {
                    navController.navigate(Destination.Main.route) {
                        popUpTo(Destination.Login.route) { inclusive = true }
                    }
                },
                onNavigateBack = {
                    navController.popBackStack()
                }
            )
        }

        composable(Destination.Main.route) {
            MainScreen(
                onNavigateToFundDetail = { fundCode ->
                    navController.navigate(Destination.FundDetail.createRoute(fundCode))
                },
                onNavigateToCompare = {
                    navController.navigate(Destination.Compare.route)
                },
                onLogout = {
                    navController.navigate(Destination.Login.route) {
                        popUpTo(Destination.Main.route) { inclusive = true }
                    }
                }
            )
        }

        composable(
            route = Destination.FundDetail.route,
            arguments = listOf(navArgument("fundCode") { type = NavType.StringType })
        ) {
            FundDetailScreen(
                onNavigateBack = { navController.popBackStack() }
            )
        }

        composable(Destination.Compare.route) {
            CompareScreen(
                onNavigateBack = { navController.popBackStack() }
            )
        }
    }
}
