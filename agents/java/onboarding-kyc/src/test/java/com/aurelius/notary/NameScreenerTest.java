package com.aurelius.notary;

import com.aurelius.notary.screening.NameScreener;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.time.LocalDate;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

/** Fuzzy screening: catches spelling variants, word order, accents; DOB cuts false positives. */
class NameScreenerTest {

    private NameScreener screener;

    @BeforeEach
    void setUp() throws Exception {
        screener = TestSupport.newAgent().screener();
    }

    @Test
    void jaroWinklerBasics() {
        assertEquals(1.0, NameScreener.jaroWinkler("martha", "martha"));
        assertEquals(0.961, Math.round(NameScreener.jaroWinkler("martha", "marhta") * 1000) / 1000.0);  // textbook value
        assertEquals(0.0, NameScreener.jaroWinkler("abc", "xyz"));
    }

    @Test
    void normalizesAccentsCaseAndPunctuation() {
        assertEquals("jose maria lopez", NameScreener.normalize("  José-María LÓPEZ "));
    }

    @Test
    void catchesSpellingVariantAndWordOrder() {
        assertEquals("potential_match", screener.screen("Victor Morozenko", null, null).result());
        assertEquals("potential_match", screener.screen("Ruiz Villanueva Carlos", null, null).result());
        assertEquals("potential_match", screener.screen("Amira Qádir", null, null).result());
    }

    @Test
    void ordinaryClientsAreClear() {
        for (String name : new String[] {"Raj Patel", "Anita Patel", "Wei Chen", "Maria Garcia"}) {
            assertEquals("clear", screener.screen(name, null, null).result(), name);
        }
    }

    @Test
    void dateOfBirthTurnsAFalsePositiveIntoClear() {
        NameScreener.Result noDob = screener.screen("Luis Garcia", null, null);
        assertEquals("potential_match", noDob.result());                  // similar to a listed alias
        assertTrue(noDob.requiresReview());
        assertEquals("clear", screener.screen("Luis Garcia", LocalDate.of(1974, 8, 30), "MX").result());
    }

    @Test
    void matchingDobRaisesTheScore() {
        double without = screener.screen("Viktor Morozenko", null, null).matches().get(0).score();
        double with = screener.screen("Viktor Morozenko", LocalDate.of(1961, 7, 19), null).matches().get(0).score();
        assertTrue(with >= without);
        assertTrue(screener.screen("Viktor Morozenko", LocalDate.of(1961, 7, 19), null).matches().get(0).reasons()
                .contains("date of birth matches"));
    }
}
