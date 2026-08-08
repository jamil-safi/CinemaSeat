import { useCallback, useEffect, useRef, useState } from "react";
import { apiRequest } from "./api.js";

const posterPalettes = [
  { a: "#594018", b: "#151515", glow: "#f0b62d" },
  { a: "#123b4b", b: "#11151b", glow: "#44b5c8" },
  { a: "#4d1d2b", b: "#151217", glow: "#dc6579" },
  { a: "#263e26", b: "#111612", glow: "#8dc96d" },
];

const terminalStates = ["CONFIRMED", "PAYMENT_FAILED", "REFUND_REQUIRED", "REFUNDED", "EXPIRED"];

function posterStyle(id) {
  const palette = posterPalettes[(Number(id) - 1) % posterPalettes.length];
  return {
    "--poster-a": palette.a,
    "--poster-b": palette.b,
    "--poster-glow": palette.glow,
  };
}

function formatDate(value, options) {
  return new Intl.DateTimeFormat(undefined, options).format(new Date(value));
}

function Header({ serviceStatus, loading, onRefresh }) {
  return (
    <header className="site-header">
      <a className="brand" href="/" aria-label="CinemaSeat home">
        <span className="brand-mark" aria-hidden="true"><i /><i /><i /></span>
        <span>Cinema<span>Seat</span></span>
      </a>
      <div className="header-actions">
        <span className={`service-status ${serviceStatus}`}>
          <span className="status-dot" aria-hidden="true" />
          <span>{serviceStatus === "online" ? "System online" : serviceStatus === "offline" ? "Service unavailable" : "Connecting"}</span>
        </span>
        <button className={`icon-button ${loading ? "loading" : ""}`} type="button" aria-label="Refresh listings" onClick={onRefresh}>
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 11a8.1 8.1 0 1 0-2.3 5.7M20 4v7h-7" /></svg>
        </button>
      </div>
    </header>
  );
}

function Hero() {
  return (
    <div className="hero shell">
      <div className="eyebrow"><span /> Now showing in Chattogram</div>
      <h1>Your perfect seat<br />is waiting.</h1>
      <p>Pick a film, choose a time, and settle in. No queues, no fuss.</p>
      <a className="primary-button hero-button" href="#movies">
        Browse showtimes
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m9 18 6-6-6-6" /></svg>
      </a>
      <div className="hero-art" aria-hidden="true">
        <div className="orb orb-one" />
        <div className="orb orb-two" />
        <div className="ticket">
          <span className="ticket-kicker">ADMIT ONE</span>
          <strong>CINEMA<br />SEAT</strong>
          <div className="ticket-rule" />
          <span>SCREEN 01 - ROW A</span>
        </div>
      </div>
    </div>
  );
}

function MovieCard({ movie, showtimes, onSelectShowtime }) {
  return (
    <article className="movie-card">
      <div className="movie-poster" style={posterStyle(movie.id)}>
        <span className="poster-number">{String(movie.id).padStart(2, "0")}</span>
      </div>
      <div className="movie-info">
        <p className="movie-meta">Now showing</p>
        <h3>{movie.title}</h3>
        <p>{movie.duration_minutes} min</p>
        <div className="showtimes" aria-label={`Showtimes for ${movie.title}`}>
          {showtimes.length ? showtimes.map((showtime) => (
            <button className="showtime-button" type="button" key={showtime.id} onClick={() => onSelectShowtime(showtime)}>
              {formatDate(showtime.starts_at, { hour: "numeric", minute: "2-digit" })}
            </button>
          )) : <span className="showtime-empty">No sessions available</span>}
        </div>
      </div>
    </article>
  );
}

function Catalog({ movies, showtimes, loading, error, onRetry, onSelectShowtime }) {
  return (
    <section className="catalog-view">
      <Hero />
      <section className="movies-section shell" id="movies" aria-labelledby="movies-heading">
        <div className="section-heading">
          <div>
            <span className="section-label">On the big screen</span>
            <h2 id="movies-heading">Now showing</h2>
          </div>
          <p>{loading ? "Loading films..." : `${movies.length} film${movies.length === 1 ? "" : "s"} playing`}</p>
        </div>
        <div className="movie-grid" aria-live="polite">
          {loading && [1, 2].map((item) => <article className="movie-card skeleton-card" key={item}><div /><span /><span /></article>)}
          {!loading && error && (
            <div className="seat-map-message">
              <p>We could not reach the cinema service.</p>
              <button className="showtime-button" type="button" onClick={onRetry}>Try again</button>
            </div>
          )}
          {!loading && !error && !movies.length && <p className="seat-map-message">No films are showing right now.</p>}
          {!loading && !error && movies.map((movie) => (
            <MovieCard
              key={movie.id}
              movie={movie}
              showtimes={showtimes.filter((showtime) => showtime.movie_id === movie.id)}
              onSelectShowtime={onSelectShowtime}
            />
          ))}
        </div>
      </section>
    </section>
  );
}

function Stepper({ step }) {
  return (
    <ol className="stepper" aria-label="Booking progress">
      {["Seats", "Verify", "Complete"].map((label, index) => {
        const itemStep = index + 1;
        const state = itemStep === step ? "active" : itemStep < step ? "complete" : "";
        return <li className={state} key={label}><span>{itemStep}</span><b>{label}</b></li>;
      })}
    </ol>
  );
}

function SeatPanel({ seats, selectedSeat, loading, onSelectSeat }) {
  return (
    <section className="seat-panel">
      <div className="panel-heading">
        <span className="section-label">Choose your spot</span>
        <h1>Select your seat</h1>
        <p>All seats in this auditorium are standard admission.</p>
      </div>
      <div className="screen-wrap" aria-hidden="true">
        <div className="screen-glow" /><div className="screen" /><span>SCREEN</span>
      </div>
      <div className="seat-map" aria-label="Cinema seat map">
        {loading && <p className="seat-map-message">Loading seats...</p>}
        {!loading && !seats.length && <p className="seat-map-message">No seats found for this showtime.</p>}
        {!loading && seats.map((seat) => {
          const unavailable = seat.status !== "AVAILABLE";
          const status = seat.status === "SOLD" ? "sold" : seat.status === "HELD" ? "temporarily held" : "available";
          return (
            <button
              className={`seat ${selectedSeat?.id === seat.id ? "selected" : ""}`}
              type="button"
              key={seat.id}
              disabled={unavailable}
              aria-label={`Seat ${seat.label}, ${status}`}
              aria-pressed={selectedSeat?.id === seat.id}
              onClick={() => onSelectSeat(seat)}
            >
              {seat.label}
            </button>
          );
        })}
      </div>
      <div className="seat-legend">
        <span><i className="legend-available" />Available</span>
        <span><i className="legend-selected" />Selected</span>
        <span><i className="legend-unavailable" />Unavailable</span>
      </div>
    </section>
  );
}

function HoldTimer({ expiresAt, onExpire }) {
  const [remaining, setRemaining] = useState(0);
  const onExpireRef = useRef(onExpire);
  onExpireRef.current = onExpire;

  useEffect(() => {
    let expired = false;
    const tick = () => {
      const next = Math.max(0, new Date(expiresAt).getTime() - Date.now());
      setRemaining(next);
      if (!next && !expired) {
        expired = true;
        onExpireRef.current();
      }
    };
    tick();
    const interval = window.setInterval(tick, 250);
    return () => window.clearInterval(interval);
  }, [expiresAt]);

  const seconds = Math.ceil(remaining / 1000);
  const value = `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
  return <strong>{value}</strong>;
}

function VerifyPanel({ hold, phone, otp, otpSent, busy, onPhoneChange, onOtpChange, onSendOtp, onVerify, onResend, onExpire }) {
  return (
    <section className="verify-panel">
      <div className="panel-heading">
        <span className="section-label">Secure checkout</span>
        <h1>Verify your number</h1>
        <p>We will use a one-time code to confirm it is really you.</p>
      </div>
      <div className="hold-alert">
        <div><span>Your seat is held for</span><HoldTimer expiresAt={hold.expires_at} onExpire={onExpire} /></div>
        <span className="pulse-ring" aria-hidden="true" />
      </div>
      {!otpSent ? (
        <form className="checkout-form" onSubmit={onSendOtp}>
          <label htmlFor="phone">Mobile number</label>
          <div className="phone-field">
            <span>+880</span>
            <input id="phone" type="tel" inputMode="numeric" autoComplete="tel" placeholder="17 0000 0000" required minLength="10" value={phone} onChange={onPhoneChange} />
          </div>
          <button className={`primary-button ${busy ? "loading" : ""}`} type="submit" disabled={busy}>Send verification code</button>
        </form>
      ) : (
        <form className="checkout-form" onSubmit={onVerify}>
          <label htmlFor="otp">Enter your verification code</label>
          <p className="form-help">A code was sent to your phone.</p>
          <input className="otp-field" id="otp" type="text" inputMode="numeric" autoComplete="one-time-code" placeholder="------" maxLength="20" required value={otp} onChange={onOtpChange} autoFocus />
          <button className={`primary-button ${busy ? "loading" : ""}`} type="submit" disabled={busy}>Verify &amp; pay</button>
          <button className="text-button centered" type="button" onClick={onResend}>Send another code</button>
        </form>
      )}
    </section>
  );
}

function ResultPanel({ result, bookingRef, onNewBooking }) {
  const pending = result?.status === "pending";
  const success = result?.status === "success";
  const label = pending ? "Payment processing" : success ? "Booking complete" : "Booking update";
  const title = pending ? "Almost there..." : success ? "You are all set." : "Payment not completed.";
  const message = pending
    ? "Your payment is being confirmed. This usually takes only a moment."
    : success
      ? "Your seat is confirmed. See you at the movies!"
      : result?.message || "Your payment could not be confirmed.";

  return (
    <section className={`result-panel ${!pending && !success ? "failure" : ""}`} aria-live="polite">
      <div className="result-icon">
        {pending || success
          ? <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m5 12 4 4L19 6" /></svg>
          : <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 8v5M12 17h.01" /><circle cx="12" cy="12" r="9" /></svg>}
      </div>
      <span className="section-label">{label}</span>
      <h1>{title}</h1>
      <p>{message}</p>
      <div className="booking-reference"><span>Booking reference</span><strong>{bookingRef || "-"}</strong></div>
      {!pending && <button className="primary-button" type="button" onClick={onNewBooking}>Book another film</button>}
    </section>
  );
}

function OrderCard({ movie, showtime, theatre, selectedSeat, busy, onHold }) {
  return (
    <aside className="order-card">
      <span className="section-label">Your booking</span>
      <div className="order-movie">
        <div className="mini-poster" style={posterStyle(movie.id)}><span>{String(movie.id).padStart(2, "0")}</span></div>
        <div><h2>{movie.title}</h2><p>{movie.duration_minutes} min</p></div>
      </div>
      <dl className="order-details">
        <div><dt>Date</dt><dd>{formatDate(showtime.starts_at, { weekday: "short", month: "short", day: "numeric" })}</dd></div>
        <div><dt>Time</dt><dd>{formatDate(showtime.starts_at, { hour: "numeric", minute: "2-digit" })}</dd></div>
        <div><dt>Cinema</dt><dd>{theatre?.name || "CinemaSeat"}</dd></div>
        <div><dt>Seat</dt><dd>{selectedSeat?.label || "Not selected"}</dd></div>
      </dl>
      <div className="order-total"><span>Total</span><strong>{selectedSeat ? `\u09F3${Number(showtime.price).toLocaleString()}` : "\u09F30"}</strong></div>
      <button className={`primary-button ${busy ? "loading" : ""}`} type="button" disabled={!selectedSeat || busy} onClick={onHold}>Hold this seat</button>
      <p className="order-note">{selectedSeat ? "The seat is held only after you continue." : "Select an available seat to continue."}</p>
    </aside>
  );
}

function BookingView({ step, movie, showtime, theatre, seats, seatsLoading, selectedSeat, hold, phone, otp, otpSent, busy, result, onBack, onSelectSeat, onHold, onPhoneChange, onOtpChange, onSendOtp, onVerify, onResend, onExpire, onNewBooking }) {
  return (
    <section className="booking-view">
      <div className="booking-shell shell">
        {step < 3 && (
          <button className="text-button back-button" type="button" onClick={onBack}>
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m15 18-6-6 6-6" /></svg> Back to films
          </button>
        )}
        <Stepper step={step} />
        <div className="booking-layout">
          <div className="booking-main">
            {step === 1 && <SeatPanel seats={seats} selectedSeat={selectedSeat} loading={seatsLoading} onSelectSeat={onSelectSeat} />}
            {step === 2 && <VerifyPanel hold={hold} phone={phone} otp={otp} otpSent={otpSent} busy={busy} onPhoneChange={onPhoneChange} onOtpChange={onOtpChange} onSendOtp={onSendOtp} onVerify={onVerify} onResend={onResend} onExpire={onExpire} />}
            {step === 3 && <ResultPanel result={result} bookingRef={hold?.booking_ref || result?.booking_ref} onNewBooking={onNewBooking} />}
          </div>
          {step < 3 && <OrderCard movie={movie} showtime={showtime} theatre={theatre} selectedSeat={selectedSeat} busy={busy} onHold={onHold} />}
        </div>
      </div>
    </section>
  );
}

function Toast({ toast, onClose }) {
  if (!toast) return null;
  return (
    <div className={`toast ${toast.type}`} role="status" aria-live="polite">
      <span>{toast.message}</span><button type="button" onClick={onClose} aria-label="Dismiss">x</button>
    </div>
  );
}

export default function App() {
  const [catalog, setCatalog] = useState({ movies: [], theatres: [], showtimes: [] });
  const [catalogLoading, setCatalogLoading] = useState(true);
  const [catalogError, setCatalogError] = useState(false);
  const [serviceStatus, setServiceStatus] = useState("connecting");
  const [view, setView] = useState("catalog");
  const [step, setStep] = useState(1);
  const [selectedMovie, setSelectedMovie] = useState(null);
  const [selectedShowtime, setSelectedShowtime] = useState(null);
  const [selectedSeat, setSelectedSeat] = useState(null);
  const [seats, setSeats] = useState([]);
  const [seatsLoading, setSeatsLoading] = useState(false);
  const [hold, setHold] = useState(null);
  const [phone, setPhone] = useState("");
  const [otp, setOtp] = useState("");
  const [otpSent, setOtpSent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [toast, setToast] = useState(null);
  const pollTimer = useRef(null);
  const toastTimer = useRef(null);

  const notify = useCallback((message, type = "info") => {
    window.clearTimeout(toastTimer.current);
    setToast({ message, type });
    toastTimer.current = window.setTimeout(() => setToast(null), 5000);
  }, []);

  const loadCatalog = useCallback(async (announce = false) => {
    setCatalogLoading(true);
    setCatalogError(false);
    try {
      const [movies, theatres, showtimes] = await Promise.all([
        apiRequest("/movies"), apiRequest("/theatres"), apiRequest("/showtimes"),
      ]);
      setCatalog({ movies, theatres, showtimes });
      setServiceStatus("online");
      if (announce) notify("Listings are up to date.");
    } catch (error) {
      setCatalogError(true);
      setServiceStatus("offline");
      if (announce) notify(error.message, "error");
    } finally {
      setCatalogLoading(false);
    }
  }, [notify]);

  useEffect(() => {
    loadCatalog();
    return () => {
      window.clearTimeout(pollTimer.current);
      window.clearTimeout(toastTimer.current);
    };
  }, [loadCatalog]);

  const loadSeats = useCallback(async (showtimeId) => {
    setSeatsLoading(true);
    try {
      const seatMap = await apiRequest(`/showtimes/${showtimeId}/seats`);
      setSeats(seatMap.seats || []);
    } catch (error) {
      setSeats([]);
      notify(error.message, "error");
    } finally {
      setSeatsLoading(false);
    }
  }, [notify]);

  const openShowtime = (showtime) => {
    setSelectedShowtime(showtime);
    setSelectedMovie(catalog.movies.find((movie) => movie.id === showtime.movie_id));
    setSelectedSeat(null);
    setHold(null);
    setStep(1);
    setView("booking");
    setResult(null);
    loadSeats(showtime.id);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const cancelHold = async () => {
    if (!hold) return;
    const currentHold = hold;
    setHold(null);
    try {
      await apiRequest(`/holds/${encodeURIComponent(currentHold.hold_id)}`, {
        method: "DELETE",
        headers: { "X-Hold-Token": currentHold.hold_token },
      });
    } catch {
      // An expired hold needs no additional user-facing error.
    }
  };

  const backToCatalog = async () => {
    if (step === 2) await cancelHold();
    setView("catalog");
    setSelectedSeat(null);
    setPhone("");
    setOtp("");
    setOtpSent(false);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const createHold = async () => {
    if (!selectedSeat || !selectedShowtime) return;
    setBusy(true);
    try {
      const created = await apiRequest("/holds", {
        method: "POST",
        body: JSON.stringify({
          showtime_id: selectedShowtime.id,
          seat_id: selectedSeat.id,
          user_ref: `web-${crypto.randomUUID?.() || Date.now()}`,
        }),
      });
      setHold(created);
      setStep(2);
      setOtpSent(false);
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (error) {
      notify(error.message, "error");
      setSelectedSeat(null);
      loadSeats(selectedShowtime.id);
    } finally {
      setBusy(false);
    }
  };

  const expireHold = useCallback(() => {
    setHold(null);
    setSelectedSeat(null);
    setStep(1);
    setOtpSent(false);
    notify("Your seat hold expired. Please choose a seat again.", "error");
    if (selectedShowtime) loadSeats(selectedShowtime.id);
  }, [loadSeats, notify, selectedShowtime]);

  const normalizedPhone = () => {
    const raw = phone.replace(/\D/g, "");
    if (raw.startsWith("880")) return raw;
    if (raw.startsWith("0")) return `88${raw}`;
    return `880${raw}`;
  };

  const sendOtp = async (event) => {
    event.preventDefault();
    setBusy(true);
    try {
      await apiRequest("/otp/send", {
        method: "POST",
        body: JSON.stringify({ booking_ref: hold.booking_ref, phone: normalizedPhone() }),
      });
      setOtpSent(true);
      notify("Verification code sent.");
    } catch (error) {
      notify(error.message, "error");
    } finally {
      setBusy(false);
    }
  };

  const pollBooking = useCallback(async (bookingRef, attempt = 0) => {
    try {
      const booking = await apiRequest(`/bookings/${encodeURIComponent(bookingRef)}`);
      if (terminalStates.includes(booking.state)) {
        const success = booking.state === "CONFIRMED";
        setResult({
          status: success ? "success" : "failure",
          booking_ref: booking.booking_ref,
          message: success ? "" : `Your booking is ${booking.state.toLowerCase().replaceAll("_", " ")}. No confirmed seat was charged.`,
        });
        if (success) setHold(null);
        return;
      }
    } catch (error) {
      if (!attempt) notify(error.message, "error");
    }

    if (attempt < 19) {
      pollTimer.current = window.setTimeout(() => pollBooking(bookingRef, attempt + 1), 1500);
    } else {
      setResult({ status: "failure", booking_ref: bookingRef, message: "Payment is still processing. Keep your booking reference and check again shortly." });
    }
  }, [notify]);

  const verifyAndPay = async (event) => {
    event.preventDefault();
    setBusy(true);
    try {
      await apiRequest("/otp/verify", {
        method: "POST",
        body: JSON.stringify({ booking_ref: hold.booking_ref, code: otp.trim() }),
      });
      await apiRequest(`/bookings/${encodeURIComponent(hold.booking_ref)}/pay`, {
        method: "POST",
        headers: { "X-Mock-Mode": "deterministic" },
      });
      setStep(3);
      setResult({ status: "pending", booking_ref: hold.booking_ref });
      pollBooking(hold.booking_ref);
    } catch (error) {
      notify(error.message, "error");
    } finally {
      setBusy(false);
    }
  };

  const newBooking = () => {
    window.clearTimeout(pollTimer.current);
    setView("catalog");
    setStep(1);
    setHold(null);
    setResult(null);
    setSelectedSeat(null);
    setPhone("");
    setOtp("");
    setOtpSent(false);
    loadCatalog();
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const selectedTheatre = catalog.theatres.find((theatre) => theatre.id === selectedShowtime?.theatre_id);

  return (
    <>
      <Header serviceStatus={serviceStatus} loading={catalogLoading} onRefresh={() => loadCatalog(true)} />
      <main>
        {view === "catalog" ? (
          <Catalog movies={catalog.movies} showtimes={catalog.showtimes} loading={catalogLoading} error={catalogError} onRetry={() => loadCatalog()} onSelectShowtime={openShowtime} />
        ) : (
          <BookingView
            step={step}
            movie={selectedMovie}
            showtime={selectedShowtime}
            theatre={selectedTheatre}
            seats={seats}
            seatsLoading={seatsLoading}
            selectedSeat={selectedSeat}
            hold={hold}
            phone={phone}
            otp={otp}
            otpSent={otpSent}
            busy={busy}
            result={result}
            onBack={backToCatalog}
            onSelectSeat={setSelectedSeat}
            onHold={createHold}
            onPhoneChange={(event) => setPhone(event.target.value)}
            onOtpChange={(event) => setOtp(event.target.value)}
            onSendOtp={sendOtp}
            onVerify={verifyAndPay}
            onResend={() => setOtpSent(false)}
            onExpire={expireHold}
            onNewBooking={newBooking}
          />
        )}
      </main>
      <Toast toast={toast} onClose={() => setToast(null)} />
      <footer><span>Copyright 2026 CinemaSeat</span><span>Made for movie nights.</span></footer>
    </>
  );
}
