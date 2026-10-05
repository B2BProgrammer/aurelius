package com.aurelius.notary.screening;

import com.fasterxml.jackson.databind.ObjectMapper;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.text.Normalizer;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Comparator;
import java.util.List;
import java.util.Locale;
import java.util.stream.Stream;

/**
 * AML watchlist screening with FUZZY name matching.
 *
 * LEARN: Exact matching is useless for sanctions screening: "Viktor" vs
 * "Victor", accents, middle names, word order. So we:
 *   1. normalize  (lowercase, strip accents and punctuation)
 *   2. compare with Jaro-Winkler similarity (0..1, rewards a shared start)
 *      on the name AND on the name with its words sorted (order-proof)
 *   3. adjust with date of birth: a different birth year lowers the score
 *      (this is how real systems cut false positives)
 * A score at or above the threshold is a POTENTIAL match: a human compliance
 * officer decides. Code never auto-accuses a client.
 */
public final class NameScreener {

    public record Entry(String listId, String name, List<String> aliases, LocalDate dob, String country, String program) {
        public Entry {
            aliases = aliases == null ? List.of() : List.copyOf(aliases);
        }
    }

    private record Watchlist(List<Entry> entries) {}

    public record Match(String listId, String listedName, String program, double score, List<String> reasons) {}

    public record Result(String result, List<Match> matches, boolean requiresReview) {}

    private final List<Entry> entries;
    private final double threshold;

    public NameScreener(List<Entry> entries, double threshold) {
        this.entries = List.copyOf(entries);
        this.threshold = threshold;
    }

    public static NameScreener load(Path file, ObjectMapper mapper, double threshold) throws IOException {
        Watchlist w = mapper.readValue(Files.readString(file), Watchlist.class);
        return new NameScreener(w.entries(), threshold);
    }

    public int size() {
        return entries.size();
    }

    public double threshold() {
        return threshold;
    }

    public Result screen(String name, LocalDate dob, String country) {
        List<Match> matches = new ArrayList<>();
        for (Entry e : entries) {
            String bestName = e.name();
            double best = 0;
            for (String candidate : Stream.concat(Stream.of(e.name()), e.aliases().stream()).toList()) {
                double s = similarity(name, candidate);
                if (s > best) { best = s; bestName = candidate; }
            }
            List<String> reasons = new ArrayList<>();
            reasons.add(String.format(Locale.ROOT, "name similarity %.2f with \"%s\"", best, bestName));
            double score = best;
            if (dob != null && e.dob() != null) {
                if (dob.equals(e.dob())) {
                    score = Math.min(1.0, score + 0.05);
                    reasons.add("date of birth matches");
                } else if (dob.getYear() != e.dob().getYear()) {
                    score *= 0.85;
                    reasons.add("birth year differs (" + dob.getYear() + " vs " + e.dob().getYear() + ")");
                }
            } else {
                reasons.add("no date of birth to compare");
            }
            if (country != null && country.equalsIgnoreCase(e.country())) reasons.add("country matches");
            if (score >= threshold) {
                matches.add(new Match(e.listId(), e.name(), e.program(), round(score), reasons));
            }
        }
        matches.sort(Comparator.comparingDouble(Match::score).reversed());
        return new Result(matches.isEmpty() ? "clear" : "potential_match", matches, !matches.isEmpty());
    }

    /** Best of: plain Jaro-Winkler, and Jaro-Winkler with words sorted ("Ruiz Carlos" == "Carlos Ruiz"). */
    public static double similarity(String a, String b) {
        String na = normalize(a), nb = normalize(b);
        return Math.max(jaroWinkler(na, nb), jaroWinkler(sortWords(na), sortWords(nb)));
    }

    public static String normalize(String s) {
        String noAccents = Normalizer.normalize(s, Normalizer.Form.NFD).replaceAll("\\p{M}", "");
        return noAccents.toLowerCase(Locale.ROOT).replaceAll("[^a-z ]", " ").replaceAll("\\s+", " ").trim();
    }

    private static String sortWords(String s) {
        String[] words = s.split(" ");
        Arrays.sort(words);
        return String.join(" ", words);
    }

    /** Jaro-Winkler similarity: 1.0 = identical, 0.0 = nothing in common. */
    public static double jaroWinkler(String s1, String s2) {
        if (s1.equals(s2)) return 1.0;
        if (s1.isEmpty() || s2.isEmpty()) return 0.0;
        int window = Math.max(0, Math.max(s1.length(), s2.length()) / 2 - 1);
        boolean[] m1 = new boolean[s1.length()], m2 = new boolean[s2.length()];
        int matches = 0;
        for (int i = 0; i < s1.length(); i++) {
            int lo = Math.max(0, i - window), hi = Math.min(s2.length() - 1, i + window);
            for (int j = lo; j <= hi; j++) {
                if (!m2[j] && s1.charAt(i) == s2.charAt(j)) {
                    m1[i] = m2[j] = true;
                    matches++;
                    break;
                }
            }
        }
        if (matches == 0) return 0.0;
        int transpositions = 0;
        for (int i = 0, k = 0; i < s1.length(); i++) {
            if (!m1[i]) continue;
            while (!m2[k]) k++;
            if (s1.charAt(i) != s2.charAt(k)) transpositions++;
            k++;
        }
        double m = matches;
        double jaro = (m / s1.length() + m / s2.length() + (m - transpositions / 2.0) / m) / 3.0;
        int prefix = 0;
        while (prefix < Math.min(4, Math.min(s1.length(), s2.length())) && s1.charAt(prefix) == s2.charAt(prefix)) prefix++;
        return jaro + prefix * 0.1 * (1 - jaro);
    }

    private static double round(double v) {
        return Math.round(v * 1000) / 1000.0;
    }
}
