package com.fundval.app.navigation

sealed class Destination(val route: String) {
    data object Login : Destination("login")
    data object Register : Destination("register")
    data object Main : Destination("main")

    // Bottom nav tabs
    data object Watchlist : Destination("main/watchlist")
    data object Funds : Destination("main/funds")
    data object Positions : Destination("main/positions")
    data object Accounts : Destination("main/accounts")
    data object Profile : Destination("main/profile")

    // Sub-routes (not tabs)
    data object FundDetail : Destination("funds/{fundCode}") {
        fun createRoute(fundCode: String) = "funds/$fundCode"
    }
    data object Compare : Destination("compare")
}
