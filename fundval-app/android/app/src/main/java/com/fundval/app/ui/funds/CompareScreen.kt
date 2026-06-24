package com.fundval.app.ui.funds

import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CompareScreen(
    onNavigateBack: () -> Unit,
    viewModel: CompareViewModel = hiltViewModel(),
    searchViewModel: FundListViewModel = hiltViewModel()
) {
    val state by viewModel.uiState.collectAsState()
    val searchState by searchViewModel.uiState.collectAsState()
    var searchQuery by remember { mutableStateOf("") }
    var showSearch by remember { mutableStateOf(false) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("基金 PK 对比") },
                navigationIcon = {
                    IconButton(onClick = onNavigateBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, "返回")
                    }
                },
                actions = {
                    TextButton(onClick = { showSearch = !showSearch }) {
                        Text(if (showSearch) "取消" else "添加")
                    }
                }
            )
        },
        contentWindowInsets = WindowInsets(0, 0, 0, 0)
    ) { padding ->
        Column(modifier = Modifier.fillMaxSize().padding(padding)) {
            // Selected fund chips
            if (state.selectedCodes.isNotEmpty()) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .horizontalScroll(rememberScrollState())
                        .padding(horizontal = 16.dp, vertical = 8.dp),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    state.selectedCodes.forEach { code ->
                        InputChip(
                            selected = true,
                            onClick = { viewModel.removeFund(code) },
                            label = { Text(code) },
                            trailingIcon = {
                                Icon(Icons.Default.Close, "移除", Modifier.size(16.dp))
                            }
                        )
                    }
                }
            }

            // Search bar (toggleable)
            if (showSearch) {
                OutlinedTextField(
                    value = searchQuery,
                    onValueChange = {
                        searchQuery = it
                        searchViewModel.onSearchQueryChange(it)
                    },
                    placeholder = { Text("搜索基金名称或代码") },
                    leadingIcon = { Icon(Icons.Default.Search, "搜索") },
                    singleLine = true,
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 16.dp, vertical = 8.dp)
                )

                // Search results (limited to 10)
                if (searchState.funds.isNotEmpty() && searchQuery.isNotBlank()) {
                    LazyColumn(
                        modifier = Modifier.heightIn(max = 300.dp),
                        contentPadding = PaddingValues(horizontal = 16.dp)
                    ) {
                        items(searchState.funds.take(10)) { fund ->
                            val alreadyAdded = state.selectedCodes.contains(fund.fundCode)
                            Surface(
                                modifier = Modifier.fillMaxWidth().clickable(enabled = !alreadyAdded) {
                                    viewModel.addFund(fund.fundCode)
                                    searchQuery = ""
                                    searchViewModel.onSearchQueryChange("")
                                },
                                tonalElevation = 1.dp
                            ) {
                                Row(
                                    modifier = Modifier.padding(12.dp),
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    Column(Modifier.weight(1f)) {
                                        Text(fund.fundName, maxLines = 1, overflow = TextOverflow.Ellipsis)
                                        Text(
                                            "${fund.fundCode} · ${fund.fundType ?: ""}",
                                            style = MaterialTheme.typography.labelSmall,
                                            color = MaterialTheme.colorScheme.onSurfaceVariant
                                        )
                                    }
                                    if (alreadyAdded) {
                                        Text("已添加", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.primary)
                                    } else {
                                        TextButton(onClick = { viewModel.addFund(fund.fundCode) }) {
                                            Text("添加")
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }

            // Comparison results
            when {
                state.isLoading -> {
                    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        CircularProgressIndicator()
                    }
                }
                state.selectedCodes.size < 2 -> {
                    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        Text(
                            if (showSearch) "搜索并添加 2-5 只基金"
                            else "点击右上角「添加」搜索基金",
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                }
                state.error != null -> {
                    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        Text(state.error ?: "", color = MaterialTheme.colorScheme.error)
                    }
                }
                state.funds.isNotEmpty() -> {
                    LazyColumn(
                        modifier = Modifier.fillMaxSize(),
                        contentPadding = PaddingValues(vertical = 8.dp)
                    ) {
                        item {
                            Row(modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp)) {
                                Spacer(Modifier.width(72.dp))
                                state.funds.forEach { fund ->
                                    Column(Modifier.weight(1f), horizontalAlignment = Alignment.CenterHorizontally) {
                                        Text(fund.fundName ?: "", fontWeight = FontWeight.Bold, textAlign = TextAlign.Center, maxLines = 2)
                                        Text(fund.fundCode, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                    }
                                }
                            }
                            HorizontalDivider()
                        }
                        item { CompareRow("最新净值", state.funds.map { it.latestNav ?: "-" }) }
                        item { CompareRow("类型", state.funds.map { it.fundType ?: "-" }) }
                        item { SectionHeader("收益率 (%)") }
                        item { CompareRow("1个月", state.funds.map { it.returns?.get("1m") ?: "-" }, isPercent = true) }
                        item { CompareRow("3个月", state.funds.map { it.returns?.get("3m") ?: "-" }, isPercent = true) }
                        item { CompareRow("6个月", state.funds.map { it.returns?.get("6m") ?: "-" }, isPercent = true) }
                        item { CompareRow("1年", state.funds.map { it.returns?.get("1y") ?: "-" }, isPercent = true) }
                        val hasMetrics = state.funds.any { it.metrics != null }
                        if (hasMetrics) {
                            item { SectionHeader("风险指标") }
                            item { CompareRow("最大回撤", state.funds.map { it.metrics?.maxDrawdown ?: "-" }, isPercent = true) }
                            item { CompareRow("波动率", state.funds.map { it.metrics?.volatility ?: "-" }, isPercent = true) }
                            item { CompareRow("夏普比率", state.funds.map { it.metrics?.sharpe ?: "-" }, highlightBest = true) }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun SectionHeader(title: String) {
    Text(
        text = title,
        style = MaterialTheme.typography.titleSmall,
        fontWeight = FontWeight.Bold,
        modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
        color = MaterialTheme.colorScheme.primary
    )
}

@Composable
private fun CompareRow(
    label: String,
    values: List<String>,
    isPercent: Boolean = false,
    highlightBest: Boolean = false
) {
    Row(
        modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 6.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text(label, style = MaterialTheme.typography.bodyMedium, modifier = Modifier.width(72.dp))
        val numericValues = values.map { it.removeSuffix("%").toDoubleOrNull() }
        val bestIdx = if (highlightBest && numericValues.all { it != null }) {
            numericValues.indices.maxByOrNull { numericValues[it]!! }
        } else null

        values.forEachIndexed { i, v ->
            Text(
                text = v,
                modifier = Modifier.weight(1f),
                textAlign = TextAlign.Center,
                style = if (bestIdx == i) MaterialTheme.typography.bodyMedium.copy(fontWeight = FontWeight.Bold)
                else MaterialTheme.typography.bodyMedium,
                color = when {
                    bestIdx == i -> Color(0xFFE53935)
                    else -> {
                        val n = numericValues[i]
                        if (n != null && n < 0) Color(0xFF43A047) else MaterialTheme.colorScheme.onSurface
                    }
                }
            )
        }
    }
}
