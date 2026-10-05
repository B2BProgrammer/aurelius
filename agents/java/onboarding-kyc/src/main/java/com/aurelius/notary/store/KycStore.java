package com.aurelius.notary.store;

import com.aurelius.notary.kyc.Model.ClientFile;
import com.aurelius.notary.kyc.Model.Document;
import com.aurelius.notary.kyc.Model.KycData;
import com.aurelius.notary.kyc.Model.Member;
import com.aurelius.notary.kyc.Model.Screening;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.file.AccessDeniedException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.TreeMap;
import java.util.function.Function;

/**
 * The KYC "database": one JSON file (stands in for the firm's onboarding system).
 *
 * LEARN, three write-safety habits (same as the Liaison, now in Java):
 *  1. synchronized: one write at a time, so two requests can't both read
 *     version 5 and both write version 6 (lost update).
 *  2. ATOMIC FILE WRITE: write kyc.json.tmp, then rename over kyc.json. A crash
 *     mid-write leaves the old file intact, never half a file.
 *     On Windows, OneDrive or antivirus can briefly lock the file: retry.
 *  3. IDEMPOTENCY: every write carries a key. Seen it before? Return the
 *     earlier result instead of writing again. Retries become safe.
 */
public class KycStore {

    public record Added(Document document, boolean duplicate) {}

    private final Path dataFile;
    private final ObjectMapper mapper;
    private KycData data;

    public KycStore(Path dataFile, Path seedFile, ObjectMapper fileMapper) {
        this.dataFile = dataFile;
        this.mapper = fileMapper;
        try {
            if (!Files.exists(dataFile)) {
                if (dataFile.getParent() != null) Files.createDirectories(dataFile.getParent());
                Files.copy(seedFile, dataFile);
            }
            this.data = mapper.readValue(Files.readString(dataFile), KycData.class);
        } catch (IOException e) {
            throw new UncheckedIOException("Cannot load KYC data from " + dataFile, e);
        }
    }

    public synchronized List<String> clientIds() {
        return new TreeMap<>(data.clients()).keySet().stream().toList();
    }

    public synchronized Optional<ClientFile> get(String clientId) {
        return Optional.ofNullable(data.clients().get(clientId));
    }

    /**
     * Add a document exactly once per idempotency key.
     * makeDocument receives the new doc_id and builds the record.
     */
    public synchronized Added addDocument(String clientId, String idempotencyKey, Function<String, Document> makeDocument) {
        String existingId = data.processed().get(idempotencyKey);
        ClientFile client = data.clients().get(clientId);
        if (client == null) throw new IllegalArgumentException("No KYC file for client '" + clientId + "'");
        if (existingId != null) {
            Document prior = client.documents().stream().filter(d -> d.docId().equals(existingId)).findFirst().orElseThrow();
            return new Added(prior, true);
        }
        String docId = "D-" + data.nextDocNumber();
        Document doc = makeDocument.apply(docId);
        Map<String, ClientFile> clients = new HashMap<>(data.clients());
        clients.put(clientId, client.withDocument(doc));
        Map<String, String> processed = new HashMap<>(data.processed());
        processed.put(idempotencyKey, docId);
        save(new KycData(clients, processed, data.nextDocNumber() + 1));
        return new Added(doc, false);
    }

    /** Record a screening result on a member (naturally idempotent: same day, same result). */
    public synchronized Member recordScreening(String clientId, String memberId, Screening screening) {
        ClientFile client = data.clients().get(clientId);
        if (client == null) throw new IllegalArgumentException("No KYC file for client '" + clientId + "'");
        Member member = client.member(memberId);
        if (member == null) throw new IllegalArgumentException("No member '" + memberId + "' in " + clientId);
        Member updated = member.withScreening(screening);
        Map<String, ClientFile> clients = new HashMap<>(data.clients());
        clients.put(clientId, client.withMember(updated));
        save(new KycData(clients, data.processed(), data.nextDocNumber()));
        return updated;
    }

    private void save(KycData next) {
        Path tmp = dataFile.resolveSibling(dataFile.getFileName() + ".tmp");
        try {
            Files.writeString(tmp, mapper.writeValueAsString(sorted(next)));
            moveWithRetry(tmp, dataFile);
            data = next;                         // only after the file is safely written
        } catch (IOException e) {
            throw new UncheckedIOException("Cannot save KYC data", e);
        }
    }

    private static void moveWithRetry(Path from, Path to) throws IOException {
        for (int attempt = 1; ; attempt++) {
            try {
                Files.move(from, to, StandardCopyOption.REPLACE_EXISTING, StandardCopyOption.ATOMIC_MOVE);
                return;
            } catch (AccessDeniedException e) {               // Windows: file briefly locked
                if (attempt >= 5) throw e;
                try {
                    Thread.sleep(50L * attempt);
                } catch (InterruptedException ie) {
                    Thread.currentThread().interrupt();
                    throw e;
                }
            }
        }
    }

    /** Stable key order in the file = readable diffs. */
    private static KycData sorted(KycData d) {
        return new KycData(new TreeMap<>(d.clients()), new TreeMap<>(d.processed()), d.nextDocNumber());
    }
}
