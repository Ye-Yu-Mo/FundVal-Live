package com.fundval.app.ui.positions

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.ChevronLeft
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.History
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.fundval.app.data.api.dto.CreateOperationRequest
import com.fundval.app.data.api.dto.PositionDto
import com.fundval.app.data.api.dto.PositionOperationDto
import com.fundval.app.ui.accounts.moneyFormat

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PositionScreen(
    viewModel: PositionViewModel = hiltViewModel()
) {
    val state by viewModel.uiState.collectAsState()
    var fundCode by remember { mutableStateOf("") }
    var opType by remember { mutableStateOf("BUY") }
    var opDate by remember { mutableStateOf("") }
    var before15 by remember { mutableStateOf(true) }
    var amount by remember { mutableStateOf("") }
    var share by remember { mutableStateOf("") }
    var nav by remember { mutableStateOf("") }

    Column(modifier = Modifier.fillMaxSize()) {
        TopAppBar(
            title = { Text(if (state.showOperations) "操作流水" else "持仓管理") },
            navigationIcon = {
                if (state.showOperations) {
                    IconButton(onClick = { viewModel.hideOperations() }) {
                        Icon(Icons.Default.ChevronLeft, "返回")
                    }
                }
            },
            actions = {
                if (!state.showOperations) {
                    IconButton(onClick = { viewModel.loadOperations() }) {
                        Icon(Icons.Default.History, "操作记录")
                    }
                }
            }
        )

        if (!state.showOperations) {
            // Account filter dropdown
            var expanded by remember { mutableStateOf(false) }
            val selectedName = state.accountNames.find { it.first == state.selectedAccountId }?.second ?: "全部账户"

            ExposedDropdownMenuBox(
                expanded = expanded,
                onExpandedChange = { expanded = it },
                modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp)
            ) {
                OutlinedTextField(
                    value = selectedName,
                    onValueChange = {},
                    readOnly = true,
                    trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded) },
                    modifier = Modifier.menuAnchor().fillMaxWidth(),
                    label = { Text("筛选账户") }
                )
                ExposedDropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
                    DropdownMenuItem(
                        text = { Text("全部账户") },
                        onClick = { viewModel.selectAccount(null); expanded = false }
                    )
                    state.accountNames.forEach { (id, name) ->
                        DropdownMenuItem(
                            text = { Text(name) },
                            onClick = { viewModel.selectAccount(id); expanded = false }
                        )
                    }
                }
            }

            when {
                state.isLoading -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    CircularProgressIndicator()
                }
                state.positions.isEmpty() -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Text("暂无持仓", color = MaterialTheme.colorScheme.onSurfaceVariant)
                        Spacer(Modifier.height(8.dp))
                        TextButton(onClick = { viewModel.showCreateDialog() }) { Text("添加第一笔操作") }
                    }
                }
                else -> LazyColumn(
                    contentPadding = PaddingValues(16.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    items(state.positions, key = { it.id }) { pos ->
                        PositionCard(position = pos)
                    }
                }
            }

            // FAB
            FloatingActionButton(
                onClick = { viewModel.showCreateDialog() },
                modifier = Modifier.padding(16.dp),
                containerColor = MaterialTheme.colorScheme.primary
            ) {
                Icon(Icons.Default.Add, "添加操作")
            }
        } else {
            // Operations list
            if (state.operations.isEmpty()) {
                Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    Text("暂无操作记录", color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            } else {
                LazyColumn(
                    contentPadding = PaddingValues(16.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    items(state.operations, key = { it.id }) { op ->
                        OperationCard(
                            operation = op,
                            onDelete = { viewModel.deleteOperation(op.id) }
                        )
                    }
                }
            }
        }
    }

    // Create operation dialog
    if (state.showCreateDialog) {
        var selectedAccount by remember { mutableStateOf(state.selectedAccountId ?: state.accountNames.firstOrNull()?.first ?: "") }
        AlertDialog(
            onDismissRequest = { viewModel.hideCreateDialog() },
            title = { Text("添加操作") },
            text = {
                LazyColumn(modifier = Modifier.heightIn(max = 400.dp)) {
                    item {
                        OutlinedTextField(value = fundCode, onValueChange = { fundCode = it }, label = { Text("基金代码") }, singleLine = true, modifier = Modifier.fillMaxWidth())
                        Spacer(Modifier.height(8.dp))
                    }
                    item {
                        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            FilterChip(selected = opType == "BUY", onClick = { opType = "BUY" }, label = { Text("买入") }, modifier = Modifier.weight(1f))
                            FilterChip(selected = opType == "SELL", onClick = { opType = "SELL" }, label = { Text("卖出") }, modifier = Modifier.weight(1f))
                        }
                        Spacer(Modifier.height(8.dp))
                    }
                    item {
                        OutlinedTextField(value = opDate, onValueChange = { opDate = it }, label = { Text("操作日期 (YYYY-MM-DD)") }, singleLine = true, modifier = Modifier.fillMaxWidth())
                        Spacer(Modifier.height(8.dp))
                    }
                    item {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text("15:00 前操作")
                            Spacer(Modifier.weight(1f))
                            Switch(checked = before15, onCheckedChange = { before15 = it })
                        }
                        Spacer(Modifier.height(8.dp))
                    }
                    item {
                        OutlinedTextField(value = amount, onValueChange = { amount = it }, label = { Text("金额") }, singleLine = true, modifier = Modifier.fillMaxWidth())
                        Spacer(Modifier.height(8.dp))
                    }
                    item {
                        OutlinedTextField(value = share, onValueChange = { share = it }, label = { Text("份额") }, singleLine = true, modifier = Modifier.fillMaxWidth())
                        Spacer(Modifier.height(8.dp))
                    }
                    item {
                        OutlinedTextField(value = nav, onValueChange = { nav = it }, label = { Text("净值") }, singleLine = true, modifier = Modifier.fillMaxWidth())
                    }
                }
            },
            confirmButton = {
                TextButton(onClick = {
                    val accountId = selectedAccount.ifBlank { state.selectedAccountId ?: state.accountNames.firstOrNull()?.first ?: "" }
                    viewModel.createOperation(CreateOperationRequest(
                        account = accountId,
                        fundCode = fundCode,
                        operationType = opType,
                        operationDate = opDate,
                        before15 = before15,
                        amount = amount,
                        share = share,
                        nav = nav
                    ))
                }, enabled = fundCode.isNotBlank() && opDate.isNotBlank() && amount.isNotBlank()) {
                    Text("添加")
                }
            },
            dismissButton = {
                TextButton(onClick = { viewModel.hideCreateDialog() }) { Text("取消") }
            }
        )
    }
}

@Composable
fun PositionCard(position: PositionDto) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp)) {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Column(Modifier.weight(1f)) {
                    Text(position.fundName ?: position.fundCode, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                    Text(
                        "${position.fundCode} · ${position.fundType ?: ""}",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
                Column(horizontalAlignment = Alignment.End) {
                    Text("份额 ${position.holdingShare ?: "-"}", style = MaterialTheme.typography.bodySmall)
                    Text("成本 ${position.holdingCost ?: "-"}", style = MaterialTheme.typography.bodySmall)
                }
            }
            Spacer(Modifier.height(8.dp))
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Text("均价 ${position.holdingNav ?: "-"}", style = MaterialTheme.typography.bodySmall)
                val pnl = position.pnl?.toDoubleOrNull() ?: 0.0
                Text(
                    "盈亏 ${moneyFormat.format(pnl)}",
                    color = if (pnl >= 0) Color(0xFFE53935) else Color(0xFF43A047),
                    style = MaterialTheme.typography.bodyMedium
                )
            }
        }
    }
}

@Composable
fun OperationCard(operation: PositionOperationDto, onDelete: () -> Unit) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Row(
            modifier = Modifier.padding(12.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column(Modifier.weight(1f)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(operation.fundName ?: operation.fundCode, fontWeight = FontWeight.Bold)
                    Spacer(Modifier.width(8.dp))
                    AssistChip(
                        onClick = {},
                        label = { Text(if (operation.operationType == "BUY") "买入" else "卖出") },
                        modifier = Modifier.height(24.dp)
                    )
                }
                Text("${operation.operationDate} · 金额 ${operation.amount} · 份额 ${operation.share}", style = MaterialTheme.typography.bodySmall)
                Text(operation.accountName ?: "", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            IconButton(onClick = onDelete) {
                Icon(Icons.Default.Delete, "删除", tint = MaterialTheme.colorScheme.error)
            }
        }
    }
}
