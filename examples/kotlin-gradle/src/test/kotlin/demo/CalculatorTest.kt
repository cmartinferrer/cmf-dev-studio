package demo
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.Assertions.assertEquals
class CalculatorTest {
    @Test fun addsNumbers() { assertEquals(5, Calculator().add(2, 3)) }
}
