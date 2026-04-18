export default function MethodologyPage() {
  return (
    <div className="max-w-3xl mx-auto">
      <h1 className="text-3xl font-bold mb-2">How We Build Your Portfolio</h1>
      <p className="text-gray-600 mb-8">
        A plain-English walk-through of what happens when you click "Generate Portfolio".
      </p>

      <section id="overview" className="bg-white p-6 rounded-xl shadow mb-6">
        <h2 className="text-2xl font-bold mb-3">The Big Picture</h2>
        <p className="text-gray-700 mb-4">
          When you submit your profile, we run a four-step pipeline to build a portfolio tailored to your goals:
        </p>
        <ol className="list-decimal list-inside space-y-2 text-gray-700">
          <li><strong>Choose stocks</strong> that match your country and preferred sectors.</li>
          <li><strong>Estimate future returns</strong> for each stock using historical data.</li>
          <li><strong>Balance the portfolio</strong> to match your risk tolerance.</li>
          <li><strong>Simulate the future</strong> to show you a range of possible outcomes.</li>
        </ol>
      </section>

      <section id="stocks" className="bg-white p-6 rounded-xl shadow mb-6">
        <h2 className="text-2xl font-bold mb-3">Choosing Stocks</h2>
        <p className="text-gray-700 mb-3">
          We start with a universe of well-known, liquid companies listed on major exchanges in your selected country.
          From that pool, we focus on the sectors you're interested in — Technology, Healthcare, and so on.
          You can also add specific tickers you want included, or exclude any you'd rather avoid.
        </p>
        <p className="text-gray-700">
          <strong>Defensive assets for conservative profiles.</strong> If you pick a conservative-to-moderate
          risk level (1, 2, or 3), we automatically add a small set of defensive assets to your portfolio's
          candidate pool: broad investment-grade bonds (AGG), intermediate Treasuries (IEF), gold (GLD), and
          defensive equity (utilities XLU and consumer staples XLP). These don't replace your sector choices —
          they're added alongside them, giving the optimizer the option to use them when a low risk cap requires
          reducing volatility. Higher risk profiles (4 and 5) don't include them automatically, since they
          conflict with an aggressive growth target.
        </p>
      </section>

      <section id="prediction" className="bg-white p-6 rounded-xl shadow mb-6">
        <h2 className="text-2xl font-bold mb-3">Estimating Future Returns</h2>
        <p className="text-gray-700 mb-3">
          For each candidate stock, we look at its historical price behavior and apply a machine-learning
          approach to estimate how it may perform over the coming weeks. These per-stock estimates feed
          the next step.
        </p>
        <p className="text-sm text-gray-500 italic">
          An estimate is not a promise — it's a quantitative guess based on patterns in past data.
        </p>
      </section>

      <section id="optimization" className="bg-white p-6 rounded-xl shadow mb-6">
        <h2 className="text-2xl font-bold mb-3">Balancing the Portfolio</h2>
        <p className="text-gray-700 mb-3">
          Once we have per-stock estimates, we solve an optimization problem: how much of each stock
          should you hold to get the best expected return at your chosen risk level?
        </p>
        <p className="text-gray-700 mb-3">
          This is based on a well-established technique called <strong>mean-variance optimization</strong>.
          The intuition: don't put all your eggs in one basket. Spreading across multiple stocks and
          sectors reduces the damage any single bad pick can cause.
        </p>
        <p className="text-gray-700 mb-3">
          To measure how different stocks move together, we use a shrinkage technique. Raw
          correlations between stocks can be misleading when the data is noisy. Shrinkage nudges
          those correlations toward a more reliable baseline, which makes the resulting portfolio
          less sensitive to random quirks in the historical data. This is a well-established
          technique in professional portfolio construction.
        </p>
        <p className="text-gray-700 mb-3">
          By default we use a method called <strong>Hierarchical Risk Parity (HRP)</strong> — a
          clustering-based approach that spreads risk across groups of stocks that tend to
          move together. HRP tends to produce more stable, diversified portfolios than
          classical mean-variance optimization, especially when the per-stock return
          estimates are noisy. We measure the resulting portfolio volatility against your
          risk profile's cap; if HRP overshoots by more than 10%, we fall back to
          mean-variance optimization with the per-stock return estimates as a tighter
          risk control.
        </p>
      </section>

      <section id="risk" className="bg-white p-6 rounded-xl shadow mb-6">
        <h2 className="text-2xl font-bold mb-3">About Risk</h2>
        <p className="text-gray-700">
          A portfolio's risk is roughly how much its value tends to swing up and down. Higher-risk
          portfolios can grow faster — but can also fall harder in bad periods. The risk level you pick
          controls how aggressive the optimizer is allowed to be.
        </p>
      </section>

      <section id="simulation" className="bg-white p-6 rounded-xl shadow mb-6">
        <h2 className="text-2xl font-bold mb-3">Simulating the Future</h2>
        <p className="text-gray-700 mb-3">
          Once the portfolio is built, we run a <strong>Monte Carlo simulation</strong>: we generate
          thousands of randomized future scenarios using the portfolio's estimated return and risk
          characteristics. Each simulation produces one possible ending value.
        </p>
        <p className="text-gray-700 mb-3">
          From those thousands of scenarios we pull out three headline numbers:
        </p>
        <ul className="list-disc list-inside space-y-1 text-gray-700">
          <li><strong>10th percentile</strong> — only 10% of simulated scenarios ended up worse than this.</li>
          <li><strong>50th percentile</strong> — the middle of the pack; half the scenarios did better, half worse.</li>
          <li><strong>90th percentile</strong> — only 10% of simulated scenarios ended up better than this.</li>
        </ul>
      </section>

      <section className="bg-yellow-50 border-2 border-yellow-200 p-6 rounded-xl mb-6">
        <h2 className="text-2xl font-bold mb-3 text-yellow-900">⚠️ Important Limitations</h2>
        <ul className="list-disc list-inside space-y-2 text-yellow-900">
          <li>Past performance is not a reliable indicator of future results.</li>
          <li>Our estimates can be wrong. Markets frequently behave in unexpected ways.</li>
          <li>This tool is for educational and exploratory purposes — it is not financial advice.</li>
          <li>Always consult a licensed financial advisor before making real investment decisions.</li>
        </ul>
      </section>

      <section id="glossary" className="bg-white p-6 rounded-xl shadow mb-6">
        <h2 className="text-2xl font-bold mb-3">Glossary</h2>
        <dl className="space-y-3 text-gray-700">
          <div><dt className="font-semibold">Risk Score</dt><dd>A measure of how volatile your portfolio's value is. Higher = bigger swings.</dd></div>
          <div><dt className="font-semibold">Allocation</dt><dd>The percentage of your total investment placed in a specific stock.</dd></div>
          <div><dt className="font-semibold">Sector</dt><dd>A broad category of businesses (Technology, Healthcare, Energy, etc.).</dd></div>
          <div><dt className="font-semibold">Diversification</dt><dd>Spreading investments across many positions to reduce risk from any one going wrong.</dd></div>
          <div><dt className="font-semibold">Percentile</dt><dd>A point in a ranked distribution. The 10th percentile is the value below which 10% of outcomes fall.</dd></div>
          <div><dt className="font-semibold">Monte Carlo Simulation</dt><dd>A technique that uses thousands of random samples to estimate a range of possible outcomes.</dd></div>
          <div><dt className="font-semibold">Horizon</dt><dd>How long you plan to keep the investment before withdrawing.</dd></div>
        </dl>
      </section>
    </div>
  );
}
