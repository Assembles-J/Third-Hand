package com.thirdhand.app

import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class DecisionWorkspaceControllerTest {
    @Test
    fun initialLoadPublishesReadyState() = runBlocking {
        val workspace = sampleWorkspace()
        val controller = DecisionWorkspaceController(
            FakeDecisionWorkspaceRepository(mutableListOf(DecisionWorkspaceLoadResult.Success(workspace))),
        )

        controller.load("600000")

        val state = controller.state.value as DecisionWorkspaceUiState.Ready
        assertEquals(workspace, state.workspace)
        assertFalse(state.refreshing)
        assertEquals(null, state.refreshError)
    }

    @Test
    fun refreshFailureKeepsLastGoodWorkspaceVisible() = runBlocking {
        val workspace = sampleWorkspace()
        val controller = DecisionWorkspaceController(
            FakeDecisionWorkspaceRepository(
                mutableListOf(
                    DecisionWorkspaceLoadResult.Success(workspace),
                    DecisionWorkspaceLoadResult.Failure("temporary network failure"),
                ),
            ),
        )

        controller.load("600000")
        controller.refresh("600000")

        val state = controller.state.value as DecisionWorkspaceUiState.Ready
        assertEquals(workspace, state.workspace)
        assertFalse(state.refreshing)
        assertEquals("temporary network failure", state.refreshError)
    }

    @Test
    fun initialEmptyIsExplicitAndNotGenericError() = runBlocking {
        val controller = DecisionWorkspaceController(
            FakeDecisionWorkspaceRepository(mutableListOf(DecisionWorkspaceLoadResult.Empty)),
        )

        controller.load("600000")

        assertTrue(controller.state.value is DecisionWorkspaceUiState.Empty)
    }

    @Test
    fun initialFailurePreservesRecoverability() = runBlocking {
        val controller = DecisionWorkspaceController(
            FakeDecisionWorkspaceRepository(
                mutableListOf(
                    DecisionWorkspaceLoadResult.Failure(
                        message = "invalid symbol",
                        recoverable = false,
                    ),
                ),
            ),
        )

        controller.load("")

        val state = controller.state.value as DecisionWorkspaceUiState.Error
        assertEquals("invalid symbol", state.message)
        assertFalse(state.recoverable)
    }

    private fun sampleWorkspace(): DecisionWorkspaceDto = DecisionWorkspaceDto(
        symbol = "600000",
        name = "Example Bank",
        decision_id = "decision-1",
        formal_action = "HOLD",
        summary = "continuity preserved",
    )
}

private class FakeDecisionWorkspaceRepository(
    private val results: MutableList<DecisionWorkspaceLoadResult>,
) : DecisionWorkspaceRepository {
    override suspend fun latest(symbol: String): DecisionWorkspaceLoadResult {
        check(results.isNotEmpty()) { "no fake Decision Workspace result left for $symbol" }
        return results.removeAt(0)
    }
}
