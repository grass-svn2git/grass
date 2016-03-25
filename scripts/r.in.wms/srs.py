"""!
@brief WMS, WMTS and NASA OnEarth drivers implemented in GRASS using GDAL Python bindings.

List of classes:
 - srs.py::Srs

(C) 2014 by the GRASS Development Team

This program is free software under the GNU General Public License
(>=v2). Read the file COPYING that comes with GRASS for details.

@author Stepan Turek <stepan.turek seznam.cz> (Based on code from OWSLib - Copyright below)
"""
# -*- coding: ISO-8859-15 -*-
# =============================================================================
# Copyright (c) 2011 Tom Kralidis
#
# Authors : Tom Kralidis <tomkralidis@gmail.com>
#
# Contact email: tomkralidis@gmail.com
# =============================================================================


class Srs:
    """Initialize a CRS construct
        :param string srs: the Coordinate reference system. Examples:
          * EPSG:<EPSG code>
          * http://www.opengis.net/def/crs/EPSG/0/<EPSG code> (URI Style 1)
          * http://www.opengis.net/gml/srs/epsg.xml#<EPSG code> (URI Style 2)
          * urn:EPSG:geographicCRS:<epsg code>
          * urn:ogc:def:crs:EPSG::4326
          * urn:ogc:def:crs:EPSG:4326
        :param string axisorder: Force / override axisorder ('xy' or 'yx')
    """

    def __init__(self, srs):
        self.id = srs
        self.naming_authority = None
        self.category = None
        self.type = None
        self.authority = None
        self.version = None
        self.code = -1
        self.axisorder = 'xy'
        self.encoding = "code"

        values = self.id.split(':')

        if self.id.find('/def/crs/') != -1:  # URI Style 1
            self.encoding = "uri"
            vals = self.id.split('/')
            self.authority = vals[5].upper()
            self.code = int(vals[-1])
        elif self.id.find('#') != -1:  # URI Style 2
            self.encoding = "uri"
            vals = self.id.split('#')
            self.authority = vals[0].split('/')[-1].split('.')[0].upper()
            self.code = int(vals[-1])
        elif len(values) > 2:  # it's a URN style
            self.naming_authority = values[1]
            self.encoding = "urn"

            if len(values) == 3:  # bogus
                pass
            elif len(values) == 4:
                self.type = values[2]
            else:
                self.category = values[2]
                self.type = values[3]
                self.authority = values[4].upper()

            if len(values) == 7:  # version, even if empty, is included
                if values[5]:
                    self.version = values[5]

            # code is always the last value
            try:
                self.code = int(values[-1])
            except:
                self.code = values[-1]

        elif len(values) == 2:  # it's an authority:code code
            self.encoding = "code"
            self.authority = values[0].upper()
            self.code = int(values[1])

        if self.code in axisorder_yx:
            self.axisorder = 'yx'

    def getcode(self):
        """Create for example "EPSG:4326" string and return back
        :returns: String code formated in "authority:code"
        """

        if self.authority is not None and self.code is not None:
            return '%s:%s' % (self.authority, self.code)
        return None

    def getcodeurn(self):
        """Create for example "urn:ogc:def:crs:EPSG::4326" string and return back
        :returns: String code formated in "urn:ogc:def:authority:code"
        """

        return 'urn:%s:def:crs:%s:%s:%s' % (
            (self.naming_authority and self.naming_authority or "ogc"),
            (self.authority or ""),
            (self.version or ""),
            (self.code or ""))

axisorder_yx = frozenset([
    4326,
    4258,
    31466,
    31467,
    31468,
    31469,
    2166,
    2167,
    2168,
    2036,
    2044,
    2045,
    2065,
    2081,
    2082,
    2083,
    2085,
    2086,
    2091,
    2092,
    2093,
    2096,
    2097,
    2098,
    2105,
    2106,
    2107,
    2108,
    2109,
    2110,
    2111,
    2112,
    2113,
    2114,
    2115,
    2116,
    2117,
    2118,
    2119,
    2120,
    2121,
    2122,
    2123,
    2124,
    2125,
    2126,
    2127,
    2128,
    2129,
    2130,
    2131,
    2132,
    2169,
    2170,
    2171,
    2172,
    2173,
    2174,
    2175,
    2176,
    2177,
    2178,
    2179,
    2180,
    2193,
    2199,
    2200,
    2206,
    2207,
    2208,
    2209,
    2210,
    2211,
    2212,
    2319,
    2320,
    2321,
    2322,
    2323,
    2324,
    2325,
    2326,
    2327,
    2328,
    2329,
    2330,
    2331,
    2332,
    2333,
    2334,
    2335,
    2336,
    2337,
    2338,
    2339,
    2340,
    2341,
    2342,
    2343,
    2344,
    2345,
    2346,
    2347,
    2348,
    2349,
    2350,
    2351,
    2352,
    2353,
    2354,
    2355,
    2356,
    2357,
    2358,
    2359,
    2360,
    2361,
    2362,
    2363,
    2364,
    2365,
    2366,
    2367,
    2368,
    2369,
    2370,
    2371,
    2372,
    2373,
    2374,
    2375,
    2376,
    2377,
    2378,
    2379,
    2380,
    2381,
    2382,
    2383,
    2384,
    2385,
    2386,
    2387,
    2388,
    2389,
    2390,
    2391,
    2392,
    2393,
    2394,
    2395,
    2396,
    2397,
    2398,
    2399,
    2400,
    2401,
    2402,
    2403,
    2404,
    2405,
    2406,
    2407,
    2408,
    2409,
    2410,
    2411,
    2412,
    2413,
    2414,
    2415,
    2416,
    2417,
    2418,
    2419,
    2420,
    2421,
    2422,
    2423,
    2424,
    2425,
    2426,
    2427,
    2428,
    2429,
    2430,
    2431,
    2432,
    2433,
    2434,
    2435,
    2436,
    2437,
    2438,
    2439,
    2440,
    2441,
    2442,
    2443,
    2444,
    2445,
    2446,
    2447,
    2448,
    2449,
    2450,
    2451,
    2452,
    2453,
    2454,
    2455,
    2456,
    2457,
    2458,
    2459,
    2460,
    2461,
    2462,
    2463,
    2464,
    2465,
    2466,
    2467,
    2468,
    2469,
    2470,
    2471,
    2472,
    2473,
    2474,
    2475,
    2476,
    2477,
    2478,
    2479,
    2480,
    2481,
    2482,
    2483,
    2484,
    2485,
    2486,
    2487,
    2488,
    2489,
    2490,
    2491,
    2492,
    2493,
    2494,
    2495,
    2496,
    2497,
    2498,
    2499,
    2500,
    2501,
    2502,
    2503,
    2504,
    2505,
    2506,
    2507,
    2508,
    2509,
    2510,
    2511,
    2512,
    2513,
    2514,
    2515,
    2516,
    2517,
    2518,
    2519,
    2520,
    2521,
    2522,
    2523,
    2524,
    2525,
    2526,
    2527,
    2528,
    2529,
    2530,
    2531,
    2532,
    2533,
    2534,
    2535,
    2536,
    2537,
    2538,
    2539,
    2540,
    2541,
    2542,
    2543,
    2544,
    2545,
    2546,
    2547,
    2548,
    2549,
    2551,
    2552,
    2553,
    2554,
    2555,
    2556,
    2557,
    2558,
    2559,
    2560,
    2561,
    2562,
    2563,
    2564,
    2565,
    2566,
    2567,
    2568,
    2569,
    2570,
    2571,
    2572,
    2573,
    2574,
    2575,
    2576,
    2577,
    2578,
    2579,
    2580,
    2581,
    2582,
    2583,
    2584,
    2585,
    2586,
    2587,
    2588,
    2589,
    2590,
    2591,
    2592,
    2593,
    2594,
    2595,
    2596,
    2597,
    2598,
    2599,
    2600,
    2601,
    2602,
    2603,
    2604,
    2605,
    2606,
    2607,
    2608,
    2609,
    2610,
    2611,
    2612,
    2613,
    2614,
    2615,
    2616,
    2617,
    2618,
    2619,
    2620,
    2621,
    2622,
    2623,
    2624,
    2625,
    2626,
    2627,
    2628,
    2629,
    2630,
    2631,
    2632,
    2633,
    2634,
    2635,
    2636,
    2637,
    2638,
    2639,
    2640,
    2641,
    2642,
    2643,
    2644,
    2645,
    2646,
    2647,
    2648,
    2649,
    2650,
    2651,
    2652,
    2653,
    2654,
    2655,
    2656,
    2657,
    2658,
    2659,
    2660,
    2661,
    2662,
    2663,
    2664,
    2665,
    2666,
    2667,
    2668,
    2669,
    2670,
    2671,
    2672,
    2673,
    2674,
    2675,
    2676,
    2677,
    2678,
    2679,
    2680,
    2681,
    2682,
    2683,
    2684,
    2685,
    2686,
    2687,
    2688,
    2689,
    2690,
    2691,
    2692,
    2693,
    2694,
    2695,
    2696,
    2697,
    2698,
    2699,
    2700,
    2701,
    2702,
    2703,
    2704,
    2705,
    2706,
    2707,
    2708,
    2709,
    2710,
    2711,
    2712,
    2713,
    2714,
    2715,
    2716,
    2717,
    2718,
    2719,
    2720,
    2721,
    2722,
    2723,
    2724,
    2725,
    2726,
    2727,
    2728,
    2729,
    2730,
    2731,
    2732,
    2733,
    2734,
    2735,
    2738,
    2739,
    2740,
    2741,
    2742,
    2743,
    2744,
    2745,
    2746,
    2747,
    2748,
    2749,
    2750,
    2751,
    2752,
    2753,
    2754,
    2755,
    2756,
    2757,
    2758,
    2935,
    2936,
    2937,
    2938,
    2939,
    2940,
    2941,
    2953,
    2963,
    3006,
    3007,
    3008,
    3009,
    3010,
    3011,
    3012,
    3013,
    3014,
    3015,
    3016,
    3017,
    3018,
    3019,
    3020,
    3021,
    3022,
    3023,
    3024,
    3025,
    3026,
    3027,
    3028,
    3029,
    3030,
    3034,
    3035,
    3038,
    3039,
    3040,
    3041,
    3042,
    3043,
    3044,
    3045,
    3046,
    3047,
    3048,
    3049,
    3050,
    3051,
    3058,
    3059,
    3068,
    3114,
    3115,
    3116,
    3117,
    3118,
    3120,
    3126,
    3127,
    3128,
    3129,
    3130,
    3131,
    3132,
    3133,
    3134,
    3135,
    3136,
    3137,
    3138,
    3139,
    3140,
    3146,
    3147,
    3150,
    3151,
    3152,
    3300,
    3301,
    3328,
    3329,
    3330,
    3331,
    3332,
    3333,
    3334,
    3335,
    3346,
    3350,
    3351,
    3352,
    3366,
    3386,
    3387,
    3388,
    3389,
    3390,
    3396,
    3397,
    3398,
    3399,
    3407,
    3414,
    3416,
    3764,
    3788,
    3789,
    3790,
    3791,
    3793,
    3795,
    3796,
    3819,
    3821,
    3823,
    3824,
    3833,
    3834,
    3835,
    3836,
    3837,
    3838,
    3839,
    3840,
    3841,
    3842,
    3843,
    3844,
    3845,
    3846,
    3847,
    3848,
    3849,
    3850,
    3851,
    3852,
    3854,
    3873,
    3874,
    3875,
    3876,
    3877,
    3878,
    3879,
    3880,
    3881,
    3882,
    3883,
    3884,
    3885,
    3888,
    3889,
    3906,
    3907,
    3908,
    3909,
    3910,
    3911,
    4001,
    4002,
    4003,
    4004,
    4005,
    4006,
    4007,
    4008,
    4009,
    4010,
    4011,
    4012,
    4013,
    4014,
    4015,
    4016,
    4017,
    4018,
    4019,
    4020,
    4021,
    4022,
    4023,
    4024,
    4025,
    4026,
    4027,
    4028,
    4029,
    4030,
    4031,
    4032,
    4033,
    4034,
    4035,
    4036,
    4037,
    4038,
    4040,
    4041,
    4042,
    4043,
    4044,
    4045,
    4046,
    4047,
    4052,
    4053,
    4054,
    4055,
    4074,
    4075,
    4080,
    4081,
    4120,
    4121,
    4122,
    4123,
    4124,
    4125,
    4126,
    4127,
    4128,
    4129,
    4130,
    4131,
    4132,
    4133,
    4134,
    4135,
    4136,
    4137,
    4138,
    4139,
    4140,
    4141,
    4142,
    4143,
    4144,
    4145,
    4146,
    4147,
    4148,
    4149,
    4150,
    4151,
    4152,
    4153,
    4154,
    4155,
    4156,
    4157,
    4158,
    4159,
    4160,
    4161,
    4162,
    4163,
    4164,
    4165,
    4166,
    4167,
    4168,
    4169,
    4170,
    4171,
    4172,
    4173,
    4174,
    4175,
    4176,
    4178,
    4179,
    4180,
    4181,
    4182,
    4183,
    4184,
    4185,
    4188,
    4189,
    4190,
    4191,
    4192,
    4193,
    4194,
    4195,
    4196,
    4197,
    4198,
    4199,
    4200,
    4201,
    4202,
    4203,
    4204,
    4205,
    4206,
    4207,
    4208,
    4209,
    4210,
    4211,
    4212,
    4213,
    4214,
    4215,
    4216,
    4218,
    4219,
    4220,
    4221,
    4222,
    4223,
    4224,
    4225,
    4226,
    4227,
    4228,
    4229,
    4230,
    4231,
    4232,
    4233,
    4234,
    4235,
    4236,
    4237,
    4238,
    4239,
    4240,
    4241,
    4242,
    4243,
    4244,
    4245,
    4246,
    4247,
    4248,
    4249,
    4250,
    4251,
    4252,
    4253,
    4254,
    4255,
    4256,
    4257,
    4259,
    4260,
    4261,
    4262,
    4263,
    4264,
    4265,
    4266,
    4267,
    4268,
    4269,
    4270,
    4271,
    4272,
    4273,
    4274,
    4275,
    4276,
    4277,
    4278,
    4279,
    4280,
    4281,
    4282,
    4283,
    4284,
    4285,
    4286,
    4287,
    4288,
    4289,
    4291,
    4292,
    4293,
    4294,
    4295,
    4296,
    4297,
    4298,
    4299,
    4300,
    4301,
    4302,
    4303,
    4304,
    4306,
    4307,
    4308,
    4309,
    4310,
    4311,
    4312,
    4313,
    4314,
    4315,
    4316,
    4317,
    4318,
    4319,
    4322,
    4324,
    4327,
    4329,
    4339,
    4341,
    4343,
    4345,
    4347,
    4349,
    4351,
    4353,
    4355,
    4357,
    4359,
    4361,
    4363,
    4365,
    4367,
    4369,
    4371,
    4373,
    4375,
    4377,
    4379,
    4381,
    4383,
    4386,
    4388,
    4417,
    4434,
    4463,
    4466,
    4469,
    4470,
    4472,
    4475,
    4480,
    4482,
    4483,
    4490,
    4491,
    4492,
    4493,
    4494,
    4495,
    4496,
    4497,
    4498,
    4499,
    4500,
    4501,
    4502,
    4503,
    4504,
    4505,
    4506,
    4507,
    4508,
    4509,
    4510,
    4511,
    4512,
    4513,
    4514,
    4515,
    4516,
    4517,
    4518,
    4519,
    4520,
    4521,
    4522,
    4523,
    4524,
    4525,
    4526,
    4527,
    4528,
    4529,
    4530,
    4531,
    4532,
    4533,
    4534,
    4535,
    4536,
    4537,
    4538,
    4539,
    4540,
    4541,
    4542,
    4543,
    4544,
    4545,
    4546,
    4547,
    4548,
    4549,
    4550,
    4551,
    4552,
    4553,
    4554,
    4555,
    4557,
    4558,
    4568,
    4569,
    4570,
    4571,
    4572,
    4573,
    4574,
    4575,
    4576,
    4577,
    4578,
    4579,
    4580,
    4581,
    4582,
    4583,
    4584,
    4585,
    4586,
    4587,
    4588,
    4589,
    4600,
    4601,
    4602,
    4603,
    4604,
    4605,
    4606,
    4607,
    4608,
    4609,
    4610,
    4611,
    4612,
    4613,
    4614,
    4615,
    4616,
    4617,
    4618,
    4619,
    4620,
    4621,
    4622,
    4623,
    4624,
    4625,
    4626,
    4627,
    4628,
    4629,
    4630,
    4631,
    4632,
    4633,
    4634,
    4635,
    4636,
    4637,
    4638,
    4639,
    4640,
    4641,
    4642,
    4643,
    4644,
    4645,
    4646,
    4652,
    4653,
    4654,
    4655,
    4656,
    4657,
    4658,
    4659,
    4660,
    4661,
    4662,
    4663,
    4664,
    4665,
    4666,
    4667,
    4668,
    4669,
    4670,
    4671,
    4672,
    4673,
    4674,
    4675,
    4676,
    4677,
    4678,
    4679,
    4680,
    4681,
    4682,
    4683,
    4684,
    4685,
    4686,
    4687,
    4688,
    4689,
    4690,
    4691,
    4692,
    4693,
    4694,
    4695,
    4696,
    4697,
    4698,
    4699,
    4700,
    4701,
    4702,
    4703,
    4704,
    4705,
    4706,
    4707,
    4708,
    4709,
    4710,
    4711,
    4712,
    4713,
    4714,
    4715,
    4716,
    4717,
    4718,
    4719,
    4720,
    4721,
    4722,
    4723,
    4724,
    4725,
    4726,
    4727,
    4728,
    4729,
    4730,
    4731,
    4732,
    4733,
    4734,
    4735,
    4736,
    4737,
    4738,
    4739,
    4740,
    4741,
    4742,
    4743,
    4744,
    4745,
    4746,
    4747,
    4748,
    4749,
    4750,
    4751,
    4752,
    4753,
    4754,
    4755,
    4756,
    4757,
    4758,
    4759,
    4760,
    4761,
    4762,
    4763,
    4764,
    4765,
    4766,
    4767,
    4768,
    4769,
    4770,
    4771,
    4772,
    4773,
    4774,
    4775,
    4776,
    4777,
    4778,
    4779,
    4780,
    4781,
    4782,
    4783,
    4784,
    4785,
    4786,
    4787,
    4788,
    4789,
    4790,
    4791,
    4792,
    4793,
    4794,
    4795,
    4796,
    4797,
    4798,
    4799,
    4800,
    4801,
    4802,
    4803,
    4804,
    4805,
    4806,
    4807,
    4808,
    4809,
    4810,
    4811,
    4812,
    4813,
    4814,
    4815,
    4816,
    4817,
    4818,
    4819,
    4820,
    4821,
    4822,
    4823,
    4824,
    4839,
    4855,
    4856,
    4857,
    4858,
    4859,
    4860,
    4861,
    4862,
    4863,
    4864,
    4865,
    4866,
    4867,
    4868,
    4869,
    4870,
    4871,
    4872,
    4873,
    4874,
    4875,
    4876,
    4877,
    4878,
    4879,
    4880,
    4883,
    4885,
    4887,
    4889,
    4891,
    4893,
    4895,
    4898,
    4900,
    4901,
    4902,
    4903,
    4904,
    4907,
    4909,
    4921,
    4923,
    4925,
    4927,
    4929,
    4931,
    4933,
    4935,
    4937,
    4939,
    4941,
    4943,
    4945,
    4947,
    4949,
    4951,
    4953,
    4955,
    4957,
    4959,
    4961,
    4963,
    4965,
    4967,
    4969,
    4971,
    4973,
    4975,
    4977,
    4979,
    4981,
    4983,
    4985,
    4987,
    4989,
    4991,
    4993,
    4995,
    4997,
    4999,
    5012,
    5013,
    5017,
    5048,
    5105,
    5106,
    5107,
    5108,
    5109,
    5110,
    5111,
    5112,
    5113,
    5114,
    5115,
    5116,
    5117,
    5118,
    5119,
    5120,
    5121,
    5122,
    5123,
    5124,
    5125,
    5126,
    5127,
    5128,
    5129,
    5130,
    5132,
    5167,
    5168,
    5169,
    5170,
    5171,
    5172,
    5173,
    5174,
    5175,
    5176,
    5177,
    5178,
    5179,
    5180,
    5181,
    5182,
    5183,
    5184,
    5185,
    5186,
    5187,
    5188,
    5224,
    5228,
    5229,
    5233,
    5245,
    5246,
    5251,
    5252,
    5253,
    5254,
    5255,
    5256,
    5257,
    5258,
    5259,
    5263,
    5264,
    5269,
    5270,
    5271,
    5272,
    5273,
    5274,
    5275,
    5801,
    5802,
    5803,
    5804,
    5808,
    5809,
    5810,
    5811,
    5812,
    5813,
    5814,
    5815,
    5816,
    20004,
    20005,
    20006,
    20007,
    20008,
    20009,
    20010,
    20011,
    20012,
    20013,
    20014,
    20015,
    20016,
    20017,
    20018,
    20019,
    20020,
    20021,
    20022,
    20023,
    20024,
    20025,
    20026,
    20027,
    20028,
    20029,
    20030,
    20031,
    20032,
    20064,
    20065,
    20066,
    20067,
    20068,
    20069,
    20070,
    20071,
    20072,
    20073,
    20074,
    20075,
    20076,
    20077,
    20078,
    20079,
    20080,
    20081,
    20082,
    20083,
    20084,
    20085,
    20086,
    20087,
    20088,
    20089,
    20090,
    20091,
    20092,
    21413,
    21414,
    21415,
    21416,
    21417,
    21418,
    21419,
    21420,
    21421,
    21422,
    21423,
    21453,
    21454,
    21455,
    21456,
    21457,
    21458,
    21459,
    21460,
    21461,
    21462,
    21463,
    21473,
    21474,
    21475,
    21476,
    21477,
    21478,
    21479,
    21480,
    21481,
    21482,
    21483,
    21896,
    21897,
    21898,
    21899,
    22171,
    22172,
    22173,
    22174,
    22175,
    22176,
    22177,
    22181,
    22182,
    22183,
    22184,
    22185,
    22186,
    22187,
    22191,
    22192,
    22193,
    22194,
    22195,
    22196,
    22197,
    25884,
    27205,
    27206,
    27207,
    27208,
    27209,
    27210,
    27211,
    27212,
    27213,
    27214,
    27215,
    27216,
    27217,
    27218,
    27219,
    27220,
    27221,
    27222,
    27223,
    27224,
    27225,
    27226,
    27227,
    27228,
    27229,
    27230,
    27231,
    27232,
    27391,
    27392,
    27393,
    27394,
    27395,
    27396,
    27397,
    27398,
    27492,
    28402,
    28403,
    28404,
    28405,
    28406,
    28407,
    28408,
    28409,
    28410,
    28411,
    28412,
    28413,
    28414,
    28415,
    28416,
    28417,
    28418,
    28419,
    28420,
    28421,
    28422,
    28423,
    28424,
    28425,
    28426,
    28427,
    28428,
    28429,
    28430,
    28431,
    28432,
    28462,
    28463,
    28464,
    28465,
    28466,
    28467,
    28468,
    28469,
    28470,
    28471,
    28472,
    28473,
    28474,
    28475,
    28476,
    28477,
    28478,
    28479,
    28480,
    28481,
    28482,
    28483,
    28484,
    28485,
    28486,
    28487,
    28488,
    28489,
    28490,
    28491,
    28492,
    29701,
    29702,
    30161,
    30162,
    30163,
    30164,
    30165,
    30166,
    30167,
    30168,
    30169,
    30170,
    30171,
    30172,
    30173,
    30174,
    30175,
    30176,
    30177,
    30178,
    30179,
    30800,
    31251,
    31252,
    31253,
    31254,
    31255,
    31256,
    31257,
    31258,
    31259,
    31275,
    31276,
    31277,
    31278,
    31279,
    31281,
    31282,
    31283,
    31284,
    31285,
    31286,
    31287,
    31288,
    31289,
    31290,
    31700
])
