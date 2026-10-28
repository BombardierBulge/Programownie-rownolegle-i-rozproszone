using System.Diagnostics;

namespace Kopalnia;

static class Program
{
    static int zloze;
    static int magazyn;

    static readonly object zamekZloza = new();
    static readonly object zamekMagazynu = new();
    static readonly object zamekKonsoli = new();

    static SemaphoreSlim semaforZloza = null!;
    static SemaphoreSlim semaforMagazynu = null!;

    static string[] statusyGornikow = [];
    static bool dziala;

    static void Main(string[] args)
    {
        if (args.Length > 0)
        {
            int n = int.Parse(args[0]);
            double czas = UruchomSymulacje(n, podglad: true);
            Console.WriteLine($"Koniec. Magazyn: {magazyn}. Czas: {czas:F2} s");
            return;
        }

        Console.WriteLine("Pomiar przyspieszenia i efektywności:");
        Console.WriteLine();

        double czasBazowy = 0;

        for (int n = 1; n <= 6; n++)
        {
            Console.WriteLine($"Symulacja dla {n} górników...");
            double czas = UruchomSymulacje(n, podglad: false);

            if (n == 1)
                czasBazowy = czas;

            double przyspieszenie = czasBazowy / czas;
            double efektywnosc = przyspieszenie / n;

            Console.WriteLine(
                $"liczba górników: {n}, czas: {czas:F2} s " +
                $"przyśpieszenie: {przyspieszenie:F2} efektywność: {efektywnosc:F2}");
            Console.WriteLine();
        }
    }

    static double UruchomSymulacje(int liczbaGornikow, bool podglad)
    {
        zloze = Konfiguracja.RozmiarZloza;
        magazyn = 0;
        semaforZloza = new SemaphoreSlim(Konfiguracja.MaxGornikowNaZlozu, Konfiguracja.MaxGornikowNaZlozu);
        semaforMagazynu = new SemaphoreSlim(Konfiguracja.MaxGornikowWMagazynie, Konfiguracja.MaxGornikowWMagazynie);
        dziala = true;

        statusyGornikow = new string[liczbaGornikow];
        for (int i = 0; i < liczbaGornikow; i++)
            statusyGornikow[i] = "Oczekuje...";

        Task? podgladTask = null;
        if (podglad)
        {
            Console.Clear();
            podgladTask = Task.Run(AktualizujPodglad);
        }

        var stoper = Stopwatch.StartNew();

        Task[] gornicy = new Task[liczbaGornikow];
        for (int i = 0; i < liczbaGornikow; i++)
        {
            int id = i + 1;
            gornicy[i] = Task.Run(() => Pracuj(id));
        }

        Task.WaitAll(gornicy);
        stoper.Stop();

        dziala = false;
        podgladTask?.Wait();

        if (podglad)
        {
            lock (zamekKonsoli)
            {
                Console.SetCursorPosition(0, liczbaGornikow + 3);
            }
        }

        return stoper.Elapsed.TotalSeconds;
    }

    static void AktualizujPodglad()
    {
        while (dziala)
        {
            WypiszStan();
            Thread.Sleep(100);
        }

        WypiszStan();
    }

    static void WypiszStan()
    {
        int stanZloza;
        int stanMagazynu;

        lock (zamekZloza)
            stanZloza = zloze;

        lock (zamekMagazynu)
            stanMagazynu = magazyn;

        lock (zamekKonsoli)
        {
            Console.SetCursorPosition(0, 0);
            Console.WriteLine($"Stan złoża: {stanZloza} jednostek węgla".PadRight(50));
            Console.WriteLine($"Stan magazynu: {stanMagazynu} jednostek węgla".PadRight(50));

            for (int i = 0; i < statusyGornikow.Length; i++)
                Console.WriteLine($"Górnik {i + 1}: {statusyGornikow[i]}".PadRight(50));
        }
    }

    static void UstawStatus(int id, string status)
    {
        statusyGornikow[id - 1] = status;
    }

    static void Pracuj(int id)
    {
        while (true)
        {
            int zaladowano = Wydobyj(id);
            if (zaladowano == 0)
                break;

            UstawStatus(id, "Transportuje do magazynu...");
            Thread.Sleep(Konfiguracja.CzasPrzejazduMs);

            Rozladuj(id, zaladowano);
        }

        UstawStatus(id, "zakończył pracę.");
    }

    static int Wydobyj(int id)
    {
        UstawStatus(id, "Czeka na złoże...");
        semaforZloza.Wait();

        UstawStatus(id, "Wydobywa węgiel...");

        int zaladowano = 0;

        while (zaladowano < Konfiguracja.PojemnoscPojazdu)
        {
            lock (zamekZloza)
            {
                if (zloze <= 0)
                    break;

                zloze--;
                zaladowano++;
            }

            Thread.Sleep(Konfiguracja.CzasWydobyciaMs);
        }

        semaforZloza.Release();
        return zaladowano;
    }

    static void Rozladuj(int id, int ilosc)
    {
        UstawStatus(id, "Czeka na magazyn...");
        semaforMagazynu.Wait();

        UstawStatus(id, "Rozładowuje węgiel...");

        for (int i = 0; i < ilosc; i++)
        {
            lock (zamekMagazynu)
                magazyn++;

            Thread.Sleep(Konfiguracja.CzasRozladunkuMs);
        }

        semaforMagazynu.Release();
    }
}
